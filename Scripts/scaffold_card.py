#!/usr/bin/env python3
"""Generate a conservative RD card implementation from structured design data."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from card_effect_templates import (
    EFFECT_TEMPLATES,
    Effect,
    EffectSequence,
    TemplateRegistryError,
)
from generate_card_placeholder import render_placeholder, resolve_label
from sync_card_design import (
    read_cards,
    read_shared_bytes,
    registration_id,
    target_from_description,
)


TYPE_MAP = {
    "攻击": "Attack",
    "技能": "Skill",
    "能力": "Power",
    "状态": "Status",
}
RARITY_MAP = {
    "初始": "Basic",
    "普通": "Common",
    "罕见": "Uncommon",
    "稀有": "Rare",
    "先古": "Ancient",
    "衍生": "Token",
}
TARGET_MAP = {
    "无": "None",
    "None": "None",
    "自身": "Self",
    "Self": "Self",
    "任意敌人": "AnyEnemy",
    "单个敌人": "AnyEnemy",
    "AnyEnemy": "AnyEnemy",
    "所有敌人": "AllEnemies",
    "AllEnemies": "AllEnemies",
    "随机敌人": "RandomEnemy",
    "RandomEnemy": "RandomEnemy",
    "任意玩家": "AnyPlayer",
    "AnyPlayer": "AnyPlayer",
    "任意队友": "AnyAlly",
    "AnyAlly": "AnyAlly",
    "所有队友": "AllAllies",
    "AllAllies": "AllAllies",
    "非生物目标": "TargetedNoCreature",
    "TargetedNoCreature": "TargetedNoCreature",
    "奥斯蒂": "Osty",
    "Osty": "Osty",
}
UNCERTAIN_TARGETS = {"待确认", "不确定", "?", "TODO"}
DEFAULT_TARGETS = {
    "Attack": "AnyEnemy",
    "Skill": "Self",
    "Power": "Self",
    "Status": "None",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class ScaffoldError(ValueError):
    """Raised when the design cannot be generated without guessing."""


@dataclass(frozen=True)
class CardSpec:
    key: str
    title: str
    registration_id: str
    card_type: str
    rarity: str
    cost: int
    upgraded_cost: int
    target: str
    effects: EffectSequence
    upgraded_effects: EffectSequence
    source_description: str
    source_upgraded_description: str
    unsupported_effects: tuple[str, ...] = ()
    unsupported_upgraded_effects: tuple[str, ...] = ()
    partial_reasons: tuple[str, ...] = ()
    effect_upgrades_supported: bool = True

    @property
    def is_complete(self) -> bool:
        return not self.partial_reasons


@dataclass(frozen=True)
class EffectParseResult:
    effects: EffectSequence
    unsupported: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate complete cards when every effect is registered, or safe "
            "unregistered partial scaffolds when effects still require manual work."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--key", help="PascalCase card key.")
    mode.add_argument(
        "--audit-workbook",
        action="store_true",
        help="Report template coverage for every card without writing files.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Workspace root; defaults to the parent directory of scripts/.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--workbook",
        type=Path,
        help="Workbook source; defaults to design/RD卡牌设计.xlsx.",
    )
    source.add_argument(
        "--snapshot",
        type=Path,
        help="JSON snapshot source, primarily for reproducible tests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and report without writing files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON for --audit-workbook.",
    )
    return parser.parse_args()


def load_cards(
    workspace: Path, workbook: Path | None, snapshot: Path | None
) -> list[dict[str, Any]]:
    if snapshot is not None:
        source = snapshot.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Card design snapshot not found: {source}")
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        cards = payload.get("cards")
        if not isinstance(cards, list):
            raise ScaffoldError(f"Snapshot has no cards list: {source}")
        return cards
    source = (workbook or workspace / "design" / "RD卡牌设计.xlsx").resolve()
    return read_cards(read_shared_bytes(source))


def split_effects(description: Any, field: str) -> list[str]:
    if not isinstance(description, str) or not description.strip():
        raise ScaffoldError(f"{field} is empty.")
    normalized = description.replace("。", "\n").replace("；", "\n")
    return [part.strip() for part in normalized.splitlines() if part.strip()]


def parse_effect(segment: str) -> Effect | None:
    try:
        return EFFECT_TEMPLATES.match(segment)
    except TemplateRegistryError as exc:
        raise ScaffoldError(str(exc)) from exc


def analyze_effect_list(description: Any, field: str) -> EffectParseResult:
    effects: list[Effect] = []
    unsupported: list[str] = []
    seen: set[str] = set()
    if not isinstance(description, str) or not description.strip():
        return EffectParseResult(
            EffectSequence(()),
            (f"{field}为空",),
        )
    for segment in split_effects(description, field):
        effect = parse_effect(segment)
        if effect is None:
            unsupported.append(segment)
            continue
        if effect.var_name in seen:
            unsupported.append(f"{segment}（重复动态变量 {effect.var_name}）")
            continue
        seen.add(effect.var_name)
        effects.append(effect)
    return EffectParseResult(EffectSequence(tuple(effects)), tuple(unsupported))


def parse_effect_list(description: Any, field: str) -> EffectSequence:
    result = analyze_effect_list(description, field)
    if result.unsupported:
        quoted = "；".join(f"“{item}”" for item in result.unsupported)
        raise ScaffoldError(f"{field} contains unsupported effects: {quoted}")
    return result.effects


def parse_integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ScaffoldError(f"{field} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ScaffoldError(f"{field} must be an integer; got {value!r}.")


def audit_cards(
    cards: list[dict[str, Any]],
    implemented_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Return template coverage for cards that are not yet registered."""

    implemented_keys = implemented_keys or set()
    cards_to_audit = [
        card for card in cards
        if str(card.get("key") or "").strip() not in implemented_keys
    ]

    template_usage: Counter[str] = Counter()
    unsupported_segments: Counter[str] = Counter()
    card_results: list[dict[str, Any]] = []
    base_clause_count = 0
    recognized_base_clause_count = 0
    fully_supported_card_count = 0
    partial_card_count = 0
    rejected_card_count = 0

    for card in cards_to_audit:
        key = str(card.get("key") or "").strip()
        description = card.get("描述")
        segments = (
            split_effects(description, "描述")
            if isinstance(description, str) and description.strip()
            else []
        )
        base_clause_count += len(segments)
        card_unsupported: list[str] = []
        for segment in segments:
            try:
                effect = parse_effect(segment)
            except ScaffoldError as exc:
                card_unsupported.append(str(exc))
                unsupported_segments[str(exc)] += 1
                continue
            if effect is None:
                card_unsupported.append(segment)
                unsupported_segments[segment] += 1
                continue
            recognized_base_clause_count += 1
            template_usage[effect.template_id] += 1

        try:
            spec = build_spec(card, allow_partial=True)
            if spec.is_complete:
                status = "supported"
                fully_supported_card_count += 1
            else:
                status = "partial"
                partial_card_count += 1
            error = None
            reasons = list(spec.partial_reasons)
        except ScaffoldError as exc:
            status = "rejected"
            error = str(exc)
            reasons = []
            rejected_card_count += 1
        card_results.append(
            {
                "key": key,
                "status": status,
                "target_input": card.get("目标"),
                "resolved_target": spec.target if error is None else None,
                "recognized": len(segments) - len(card_unsupported),
                "clauses": len(segments),
                "unsupported": card_unsupported,
                "partial_reasons": reasons,
                "error": error,
            }
        )

    return {
        "workbook_card_count": len(cards),
        "implemented_card_count": len(cards) - len(cards_to_audit),
        "unimplemented_card_count": len(cards_to_audit),
        "card_count": len(cards_to_audit),
        "fully_supported_card_count": fully_supported_card_count,
        "partial_card_count": partial_card_count,
        "rejected_card_count": rejected_card_count,
        "base_clause_count": base_clause_count,
        "recognized_base_clause_count": recognized_base_clause_count,
        "template_usage": dict(sorted(template_usage.items())),
        "unsupported_segments": [
            {"segment": segment, "count": count}
            for segment, count in unsupported_segments.most_common()
        ],
        "cards": card_results,
    }


def _unsupported_reason(field: str, segments: tuple[str, ...]) -> str:
    quoted = "；".join(f"“{item}”" for item in segments)
    return f"{field} contains unsupported effects: {quoted}"


def _effect_shape(effects: EffectSequence) -> list[tuple[str, str]]:
    return [
        EFFECT_TEMPLATES.get(effect.template_id).shape_key(effect)
        for effect in effects
    ]


def build_spec(
    card: dict[str, Any], *, allow_partial: bool = False
) -> CardSpec:
    key = str(card.get("key") or "").strip()
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", key):
        raise ScaffoldError(f"Card key is not PascalCase: {key!r}")
    card_type_raw = card.get("类型")
    if card_type_raw not in TYPE_MAP:
        raise ScaffoldError(f"Unsupported 类型: {card_type_raw!r}")
    card_type = TYPE_MAP[card_type_raw]
    partial_reasons: list[str] = []
    if card_type not in {"Attack", "Skill"}:
        partial_reasons.append(
            f"类型 {card_type_raw!r} currently supports partial scaffolding only."
        )

    rarity_raw = card.get("稀有度")
    if card_type == "Status" and rarity_raw in {None, "", "状态"}:
        rarity = "Status"
    elif rarity_raw in RARITY_MAP:
        rarity = RARITY_MAP[rarity_raw]
    else:
        raise ScaffoldError(f"Unsupported 稀有度: {rarity_raw!r}")

    cost = parse_integer(card.get("费用"), "费用")
    try:
        upgraded_cost = parse_integer(card.get("升级后费用"), "升级后费用")
    except ScaffoldError:
        if not allow_partial or card.get("升级后费用") not in {None, ""}:
            raise
        upgraded_cost = cost
        partial_reasons.append("升级后费用为空；骨架暂用基础费用。")
    if cost < 0 or upgraded_cost < 0:
        raise ScaffoldError("费用 and 升级后费用 must be non-negative.")

    source_description = str(card.get("描述") or "").strip()
    source_upgraded_description = str(card.get("升级后描述") or "").strip()
    parsed = analyze_effect_list(card.get("描述"), "描述")
    upgraded_parsed = analyze_effect_list(
        card.get("升级后描述"), "升级后描述"
    )
    if parsed.unsupported:
        partial_reasons.append(_unsupported_reason("描述", parsed.unsupported))
    if upgraded_parsed.unsupported:
        partial_reasons.append(
            _unsupported_reason("升级后描述", upgraded_parsed.unsupported)
        )

    shape = _effect_shape(parsed.effects)
    upgraded_shape = _effect_shape(upgraded_parsed.effects)
    effect_upgrades_supported = shape == upgraded_shape
    if not effect_upgrades_supported:
        partial_reasons.append(
            "Upgrade changes recognized effect kinds or order; effect upgrades require manual review."
        )

    targets = {
        target
        for effect in parsed.effects
        if (target := EFFECT_TEMPLATES.get(effect.template_id).target) is not None
    }
    if len(targets) > 1:
        raise ScaffoldError(
            f"Effect templates require conflicting targets: {sorted(targets)}"
        )
    target_raw = str(card.get("目标") or "").strip()
    default_target = DEFAULT_TARGETS[card_type]
    description_targets = {
        inferred
        for description in (card.get("描述"), card.get("升级后描述"))
        if (inferred := target_from_description(description)) is not None
    }
    if len(description_targets) > 1:
        raise ScaffoldError(
            f"Base and upgraded descriptions imply conflicting targets: "
            f"{sorted(description_targets)}"
        )
    inferred_target = next(iter(targets or description_targets), default_target)
    if target_raw in UNCERTAIN_TARGETS:
        target = inferred_target
        partial_reasons.append(
            f"备注中的目标标记为{target_raw!r}；骨架暂用 TargetType.{target}。"
        )
    elif target_raw:
        if target_raw not in TARGET_MAP:
            allowed = "、".join(TARGET_MAP)
            raise ScaffoldError(
                f"Unsupported 目标: {target_raw!r}; allowed values: {allowed}"
            )
        target = TARGET_MAP[target_raw]
        if targets and target not in targets:
            partial_reasons.append(
                f"显式目标 TargetType.{target} 与已识别效果需要的 "
                f"{sorted(targets)} 不一致。"
            )
    else:
        target = inferred_target

    if partial_reasons and not allow_partial:
        raise ScaffoldError(partial_reasons[0])

    return CardSpec(
        key=key,
        title=str(card.get("名称") or key).strip(),
        registration_id=registration_id(key),
        card_type=card_type,
        rarity=rarity,
        cost=cost,
        upgraded_cost=upgraded_cost,
        target=target,
        effects=parsed.effects,
        upgraded_effects=upgraded_parsed.effects,
        source_description=source_description,
        source_upgraded_description=source_upgraded_description,
        unsupported_effects=parsed.unsupported,
        unsupported_upgraded_effects=upgraded_parsed.unsupported,
        partial_reasons=tuple(partial_reasons),
        effect_upgrades_supported=effect_upgrades_supported,
    )


def dynamic_var_line(effect: Effect) -> str | None:
    return EFFECT_TEMPLATES.get(effect.template_id).dynamic_var_line(effect)


def hover_tip_line(effect: Effect) -> str | None:
    return EFFECT_TEMPLATES.get(effect.template_id).hover_tip_line(effect)


def keyword_line(effect: Effect) -> str | None:
    return EFFECT_TEMPLATES.get(effect.template_id).keyword_line(effect)


def play_lines(effect: Effect) -> list[str]:
    return EFFECT_TEMPLATES.get(effect.template_id).play_lines(effect)


def upgrade_line(effect: Effect, upgraded: Effect) -> str | None:
    delta = upgraded.value - effect.value
    if delta == 0:
        return None
    return EFFECT_TEMPLATES.get(effect.template_id).upgrade_line(effect, delta)


def localization_line(effect: Effect) -> str:
    return EFFECT_TEMPLATES.get(effect.template_id).localization_line(effect)


def effect_number_indices(
    description: str, effects: EffectSequence
) -> dict[str, int]:
    wanted = {effect.var_name for effect in effects}
    indices: dict[str, int] = {}
    number_offset = 0
    for segment in split_effects(description, "description"):
        matches = list(
            re.finditer(
                r"(?<![A-Za-z0-9_])-?[0-9]+(?:\.[0-9]+)?(?![A-Za-z0-9_])",
                segment,
            )
        )
        effect = parse_effect(segment)
        if effect is not None and effect.var_name in wanted:
            local_index = next(
                (
                    index
                    for index, match in enumerate(matches)
                    if int(match.group(0)) == effect.value
                ),
                None,
            )
            if local_index is not None:
                indices[effect.var_name] = number_offset + local_index
        number_offset += len(matches)
    return indices


def indent_lines(lines: list[str], spaces: int) -> list[str]:
    prefix = " " * spaces
    return [prefix + line if line else "" for line in lines]


def render_card(spec: CardSpec) -> str:
    templates = [
        EFFECT_TEMPLATES.get(effect.template_id) for effect in spec.effects
    ]
    needs_hover = any(template.requires_hover for template in templates)
    needs_value_props = any(
        template.requires_value_props for template in templates
    )
    needs_powers = any(template.requires_powers for template in templates)
    usings = [
        "using MegaCrit.Sts2.Core.Commands;",
        "using MegaCrit.Sts2.Core.Entities.Cards;",
        "using MegaCrit.Sts2.Core.GameActions.Multiplayer;",
    ]
    if needs_hover:
        usings.append("using MegaCrit.Sts2.Core.HoverTips;")
    usings.append("using MegaCrit.Sts2.Core.Localization.DynamicVars;")
    if needs_value_props:
        usings.append("using MegaCrit.Sts2.Core.ValueProps;")
    usings.append("using RDmod.Characters;")
    if needs_powers:
        usings.append("using RDmod.Powers;")
    if spec.is_complete:
        usings.append("using STS2RitsuLib.Interop.AutoRegistration;")
    usings.append("using STS2RitsuLib.Scaffolding.Content;")
    body: list[str] = [
        *usings,
        "",
        "namespace RDmod.Cards;",
        "",
    ]
    if spec.is_complete:
        body.append("[RegisterCard(typeof(RainbowDashCardPool))]")
    else:
        body.extend(
            [
                "// PARTIAL SCAFFOLD: intentionally not registered.",
                "// Add RegisterCard only after every TODO below is implemented and verified.",
            ]
        )
        for reason in spec.partial_reasons:
            body.append(f"// TODO(scaffold): {reason}")
    body.extend(
        [
            f"public sealed class {spec.key} : ModCardTemplate",
            "{",
        ]
    )
    for segment in spec.unsupported_effects:
        body.append(f"    // TODO(scaffold-effect): {segment}")
    for segment in spec.unsupported_upgraded_effects:
        body.append(f"    // TODO(scaffold-upgrade-effect): {segment}")
    if spec.unsupported_effects or spec.unsupported_upgraded_effects:
        body.append("")
    if any(template.gains_block for template in templates):
        body.extend(["    public override bool GainsBlock => true;", ""])
    body.extend(
        [
            "    public override CardAssetProfile AssetProfile => new(",
            '        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"',
            "    );",
            "",
        ]
    )
    keyword_lines = [
        line
        for effect in spec.effects
        if (line := keyword_line(effect)) is not None
    ]
    if keyword_lines:
        body.extend(
            [
                "    public override IEnumerable<CardKeyword> CanonicalKeywords =>",
                "    [",
            ]
        )
        body.extend(
            f"        {line}{',' if index < len(keyword_lines) - 1 else ''}"
            for index, line in enumerate(keyword_lines)
        )
        body.extend(["    ];", ""])
    body.extend(
        [
            "    protected override IEnumerable<DynamicVar> CanonicalVars =>",
            "    [",
        ]
    )
    base_indices = effect_number_indices(
        spec.source_description, spec.effects
    )
    upgrade_indices = effect_number_indices(
        spec.source_upgraded_description, spec.upgraded_effects
    )
    var_entries = [
        (effect, line)
        for effect in spec.effects
        if (line := dynamic_var_line(effect)) is not None
    ]
    for index, (effect, line) in enumerate(var_entries):
        if effect.var_name in base_indices:
            annotation = f"base[{base_indices[effect.var_name]}]"
            if effect.var_name in upgrade_indices:
                annotation += f", upgrade[{upgrade_indices[effect.var_name]}]"
            body.append(f"        // RDDesign: {annotation}")
        suffix = "," if index < len(var_entries) - 1 else ""
        body.append(f"        {line}{suffix}")
    body.extend(["    ];", ""])
    hover_lines = [
        line
        for effect in spec.effects
        if (line := hover_tip_line(effect)) is not None
    ]
    if hover_lines:
        body.extend(
            [
                "    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>",
                "    [",
            ]
        )
        body.extend(
            f"        {line}{',' if index < len(hover_lines) - 1 else ''}"
            for index, line in enumerate(hover_lines)
        )
        body.extend(["    ];", ""])
    body.extend(
        [
            f"    public {spec.key}() : base({spec.cost}, CardType.{spec.card_type}, "
            f"CardRarity.{spec.rarity}, TargetType.{spec.target})",
            "    {",
            "    }",
            "",
            "    protected override async Task OnPlay(",
            "        PlayerChoiceContext choiceContext,",
            "        CardPlay cardPlay)",
            "    {",
        ]
    )
    if spec.target == "AnyEnemy":
        body.extend(["        ArgumentNullException.ThrowIfNull(cardPlay.Target);", ""])
    for index, effect in enumerate(spec.effects):
        body.extend(indent_lines(play_lines(effect), 8))
        if index < len(spec.effects) - 1:
            body.append("")
    if not spec.effects:
        body.append("        await Task.CompletedTask;")
    body.extend(["    }", ""])
    upgrades: list[str] = []
    cost_delta = spec.upgraded_cost - spec.cost
    if cost_delta:
        upgrades.append(f"EnergyCost.UpgradeBy({cost_delta});")
    if spec.effect_upgrades_supported:
        upgrades.extend(
            line
            for effect, upgraded in zip(
                spec.effects, spec.upgraded_effects, strict=True
            )
            if (line := upgrade_line(effect, upgraded)) is not None
        )
    if not upgrades and spec.is_complete:
        raise ScaffoldError("Upgrade has no supported cost or numeric effect change.")
    body.extend(["    protected override void OnUpgrade()", "    {"])
    if upgrades:
        body.extend(indent_lines(upgrades, 8))
    else:
        body.append("        // TODO(scaffold): implement the remaining upgrade behavior.")
    body.extend(["    }", "}", ""])
    return "\n".join(body)


def render_localization(spec: CardSpec) -> tuple[str, str]:
    if spec.is_complete:
        description = "\n".join(
            line
            for effect in spec.effects
            if (line := localization_line(effect))
        )
    else:
        description = spec.source_description
    return spec.title, description


def load_localization(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ScaffoldError(f"Localization root must be an object: {path}")
    return payload


def write_scaffold(
    workspace: Path,
    spec: CardSpec,
    dry_run: bool,
    design_card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from build_card_design_mappings import candidate_for_card
    from card_design_apply import atomic_write_group

    card_path = workspace / "Mod" / "Cards" / f"{spec.key}.cs"
    localization_path = (
        workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json"
    )
    art_path = (
        workspace
        / "Mod"
        / "RDMod"
        / "images"
        / "cards"
        / f"{spec.key}.png"
    )
    mapping_path = workspace / "design" / "card-design-mappings.json"
    title_key = f"{spec.registration_id}.title"
    description_key = f"{spec.registration_id}.description"
    if card_path.exists():
        raise ScaffoldError(f"Card implementation already exists: {card_path}")
    localization = load_localization(localization_path)
    collisions = [
        key for key in (title_key, description_key) if key in localization
    ]
    if collisions:
        raise ScaffoldError(
            f"Localization keys already exist: {', '.join(collisions)}"
        )

    card_text = render_card(spec)
    mapping_source = design_card or {
        "key": spec.key,
        "描述": spec.source_description,
        "升级后描述": spec.source_upgraded_description,
    }
    mapping_candidate = candidate_for_card(
        workspace,
        mapping_source,
        source_override=card_text,
        require_registered=False,
    )
    if mapping_candidate is None:
        raise ScaffoldError(f"Unable to generate mapping candidate for {spec.key}")
    mapping_payload = (
        json.loads(mapping_path.read_text(encoding="utf-8-sig"))
        if mapping_path.is_file()
        else {"schemaVersion": 1, "cards": {}}
    )
    mapping_cards = mapping_payload.get("cards")
    if mapping_payload.get("schemaVersion") != 1 or not isinstance(mapping_cards, dict):
        raise ScaffoldError(f"Unsupported card design mapping schema: {mapping_path}")
    if spec.key in mapping_cards:
        raise ScaffoldError(f"Card mapping already exists: {spec.key}")
    merged_mapping_cards = dict(mapping_cards)
    merged_mapping_cards[spec.key] = mapping_candidate
    merged_mapping = {
        "schemaVersion": 1,
        "cards": dict(sorted(merged_mapping_cards.items())),
    }
    mapping_text = json.dumps(merged_mapping, ensure_ascii=False, indent=2) + "\n"
    mapping_effects = len(mapping_candidate["effects"])
    mapping_manual = len(mapping_candidate["audit"].get("manualNumbers", []))

    title, description = render_localization(spec)
    localization[title_key] = title
    localization[description_key] = description
    localization_text = json.dumps(
        localization, ensure_ascii=False, indent=4
    ) + "\n"
    art_status = "reused" if art_path.exists() else "generated"

    if not dry_run:
        payloads = {
            card_path: card_text.encode("utf-8"),
            localization_path: localization_text.encode("utf-8"),
        }
        if not art_path.exists():
            display_name = spec.title if spec.title != spec.key else ""
            payloads[art_path] = render_placeholder(
                resolve_label(spec.key, display_name),
                spec.card_type,
            )
        if spec.is_complete:
            payloads[mapping_path] = mapping_text.encode("utf-8")
        atomic_write_group(payloads)

    if dry_run:
        mapping_status = "preview"
    elif spec.is_complete:
        mapping_status = "written"
    else:
        mapping_status = "pending"
    return {
        "card": card_path.resolve().as_posix(),
        "localization": localization_path.resolve().as_posix(),
        "art": art_path.resolve().as_posix(),
        "art_status": art_status,
        "mapping": mapping_path.resolve().as_posix(),
        "mapping_status": mapping_status,
        "mapping_effects": mapping_effects,
        "mapping_manual": mapping_manual,
        "status": "complete" if spec.is_complete else "partial",
    }


def registered_card_keys(workspace: Path) -> set[str]:
    cards_dir = workspace / "Mod" / "Cards"
    return {
        path.stem
        for path in cards_dir.glob("*.cs")
        if "[RegisterCard" in path.read_text(encoding="utf-8-sig")
    }


def main() -> int:
    args = parse_args()
    workspace = (
        args.workspace_root.resolve()
        if args.workspace_root is not None
        else Path(__file__).resolve().parent.parent
    )
    cards = load_cards(
        workspace, args.workbook, args.snapshot
    )
    if args.audit_workbook:
        report = audit_cards(cards, registered_card_keys(workspace))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(
                "CARD_SCAFFOLD_AUDIT "
                f"cards={report['workbook_card_count']} "
                f"implemented={report['implemented_card_count']} "
                f"unimplemented={report['unimplemented_card_count']} "
                f"supported={report['fully_supported_card_count']} "
                f"partial={report['partial_card_count']} "
                f"rejected={report['rejected_card_count']} "
                f"clauses={report['base_clause_count']} "
                f"recognized={report['recognized_base_clause_count']}"
            )
            for template_id, count in report["template_usage"].items():
                print(f"  template {template_id}: {count}")
            for item in report["unsupported_segments"][:20]:
                print(f"  unsupported x{item['count']}: {item['segment']}")
            for card in report["cards"]:
                if card["target_input"] in UNCERTAIN_TARGETS:
                    print(
                        f"  target-review {card['key']}: "
                        f"{card['target_input']} -> {card['resolved_target']}"
                    )
        return 0

    assert args.key is not None
    matches = [
        card
        for card in cards
        if str(card.get("key") or "").strip() == args.key
    ]
    if not matches:
        raise ScaffoldError(
            f"Card key not found in design source: {args.key}"
        )
    if len(matches) > 1:
        raise ScaffoldError(
            f"Duplicate card key in design source: {args.key}"
        )
    spec = build_spec(matches[0], allow_partial=True)
    outputs = write_scaffold(workspace, spec, args.dry_run, matches[0])
    effects = ",".join(effect.kind for effect in spec.effects)
    if args.dry_run:
        mode = "DRY_RUN_COMPLETE" if spec.is_complete else "DRY_RUN_PARTIAL"
    else:
        mode = "CREATED" if spec.is_complete else "CREATED_PARTIAL"
    print(
        f"CARD_SCAFFOLD_{mode} key={spec.key} "
        f"id={spec.registration_id} type={spec.card_type} "
        f"rarity={spec.rarity} target={spec.target} "
        f"effects={effects} art={outputs['art_status']}"
    )
    print(f"  card: {outputs['card']}")
    print(f"  localization: {outputs['localization']}")
    print(f"  art: {outputs['art']}")
    print(
        f"  mapping: {outputs['mapping']} "
        f"status={outputs['mapping_status']} "
        f"auto={outputs['mapping_effects']} "
        f"manual={outputs['mapping_manual']}"
    )
    if not spec.is_complete:
        for reason in spec.partial_reasons:
            print(f"  todo: {reason}")
    print(
        "  next: review tutorials and official source, then build and "
        "verify before acceptance"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CARD_SCAFFOLD_ERROR {exc}", file=sys.stderr)
        raise SystemExit(1)


