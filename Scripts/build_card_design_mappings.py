#!/usr/bin/env python3
"""Build reviewable card-design mappings from explicit RDDesign annotations."""

from __future__ import annotations

import argparse
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from card_design_apply import (
    CardDesignApplyError,
    _constant_edit,
    _constructor_args,
    _dynamic_target,
    _dynamic_vars,
    _numbers,
    _upgrade_edit,
)


RDDESIGN_RE = re.compile(
    r"^[ \t]*//[ \t]*RDDesign:[ \t]*"
    r"base\[(?P<base>[0-9]+)\]"
    r"(?:[ \t]*,[ \t]*upgrade\[(?P<upgrade>[0-9]+)\])?"
    r"(?:[ \t]*,[ \t]*localization\[(?P<localization>[0-9]+)\])?"
    r"[ \t]*\r?$",
    re.MULTILINE,
)
RDDESIGN_MANUAL_RE = re.compile(
    r"^[ \t]*//[ \t]*RDDesignManual:[ \t]*"
    r"base\[(?P<base>[0-9]+)\]"
    r"(?:[ \t]*,[ \t]*upgrade\[(?P<upgrade>[0-9]+)\])?"
    r"[ \t]+-[ \t]+(?P<reason>[^\r\n]+?)[ \t]*\r?$",
    re.MULTILINE,
)
RDDESIGN_MANUAL_UPGRADE_RE = re.compile(
    r"^[ \t]*//[ \t]*RDDesignManualUpgrade:[ \t]*"
    r"upgrade\[(?P<upgrade>[0-9]+)\]"
    r"[ \t]+-[ \t]+(?P<reason>[^\r\n]+?)[ \t]*\r?$",
    re.MULTILINE,
)
CONSTANT_RE = re.compile(
    r"(?:(?:public|private|protected|internal)\s+)?"
    r"(?:static\s+)?const\s+(?:int|decimal|float|double)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<value>-?[0-9]+(?:\.[0-9]+)?)(?:[mMdDfF]?)\s*;"
)


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Print mappings for registered cards from RDDesign annotations."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=workspace / "design" / "card-design-snapshots" / "current.json",
    )
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument(
        "--write",
        action="store_true",
        help="Atomically write mappings instead of printing candidates.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=workspace / "design" / "card-design-mappings.json",
    )
    return parser.parse_args()


def _checked_index(
    key: str,
    field: str,
    raw_index: str | None,
    numbers: list[Decimal],
) -> int | None:
    if raw_index is None:
        return None
    index = int(raw_index)
    if index >= len(numbers):
        raise CardDesignApplyError(
            f"{key}: RDDesign {field}[{index}] is out of range; "
            f"description contains {len(numbers)} numbers"
        )
    return index


def _next_code_position(source: str, annotation_end: int) -> int:
    whitespace = re.match(r"\s*", source[annotation_end:])
    assert whitespace is not None
    return annotation_end + whitespace.end()


def _dynamic_target_mapping(variable: Any) -> dict[str, Any]:
    target: dict[str, Any] = {
        "kind": "dynamicVar",
        "type": variable.type_name,
        "ordinal": variable.ordinal,
        "expectedName": variable.name,
    }
    if variable.value_props:
        target["expectedValueProps"] = variable.value_props
    return target


def _annotated_effect(
    source: str,
    key: str,
    annotation: re.Match[str],
    variables: list[Any],
    base_numbers: list[Decimal],
    upgraded_numbers: list[Decimal],
) -> tuple[dict[str, Any], tuple[str, Any]]:
    base_index = _checked_index(key, "base", annotation.group("base"), base_numbers)
    assert base_index is not None
    upgrade_index = _checked_index(
        key, "upgrade", annotation.group("upgrade"), upgraded_numbers
    )
    position = _next_code_position(source, annotation.end())
    variable = next(
        (item for item in variables if item.declaration_start == position),
        None,
    )
    if variable is not None:
        target = _dynamic_target_mapping(variable)
        base_value = base_numbers[base_index]
        upgraded_value = (
            upgraded_numbers[upgrade_index]
            if upgrade_index is not None
            else base_value
        )
        match = _dynamic_target(source, key, target, base_value)
        _upgrade_edit(
            source,
            key,
            match.name,
            upgraded_value - base_value,
            upgraded_value - base_value,
        )
        target_id: tuple[str, Any] = ("dynamicVar", variable.declaration_start)
    else:
        constant = CONSTANT_RE.match(source, position)
        if constant is None:
            line = source.count("\n", 0, annotation.start()) + 1
            raise CardDesignApplyError(
                f"{key}: RDDesign annotation on line {line} must be immediately "
                "followed by a DynamicVar or named numeric constant"
            )
        target = {"kind": "constant", "name": constant.group("name")}
        base_value = base_numbers[base_index]
        _constant_edit(source, key, target, base_value, base_value)
        if upgrade_index is not None and upgraded_numbers[upgrade_index] != base_value:
            raise CardDesignApplyError(
                f"{key}: constant {constant.group('name')} cannot represent "
                "different base and upgraded values"
            )
        target_id = ("constant", constant.group("name"))

    source_mapping: dict[str, int] = {"baseNumberIndex": base_index}
    if upgrade_index is not None:
        source_mapping["upgradeNumberIndex"] = upgrade_index
    effect = {"source": source_mapping, "target": target}
    localization_index = annotation.group("localization")
    if localization_index is not None:
        effect["localizationNumberIndex"] = int(localization_index)
    return effect, target_id


def candidate_for_card(
    workspace: Path,
    card: dict[str, Any],
    *,
    source_override: str | None = None,
    require_registered: bool = True,
) -> dict[str, Any] | None:
    key = str(card["key"])
    if source_override is None:
        card_path = workspace / "Mod" / "Cards" / f"{key}.cs"
        if not card_path.is_file():
            return None
        with card_path.open("r", encoding="utf-8-sig", newline="") as stream:
            source = stream.read()
    else:
        source = source_override
    if require_registered and "[RegisterCard" not in source:
        return None

    constructor_args = _constructor_args(source, key)
    constructor = {
        "rarity": constructor_args[2][2].strip().removeprefix("CardRarity."),
        "target": constructor_args[3][2].strip().removeprefix("TargetType."),
    }
    try:
        variables = _dynamic_vars(source, key)
    except CardDesignApplyError:
        variables = []

    description_key = "\u63cf\u8ff0"
    upgraded_description_key = "\u5347\u7ea7\u540e\u63cf\u8ff0"
    if (
        str(card.get("稀有度") or "").strip() == "弃用"
        and not str(card.get(description_key) or "").strip()
        and not str(card.get(upgraded_description_key) or "").strip()
    ):
        return {
            "constructor": constructor,
            "effects": [],
            "audit": {
                "manualNumbers": [],
                "unmappedBaseNumberIndices": [],
                "unmappedUpgradeNumberIndices": [],
            },
        }
    base_numbers = _numbers(card.get(description_key), f"{key} description")
    upgraded_numbers = (
        _numbers(card.get(upgraded_description_key), f"{key} upgraded description")
        if card.get(upgraded_description_key)
        else []
    )
    effects: list[dict[str, Any]] = []
    manual_numbers: list[dict[str, Any]] = []
    used_base: set[int] = set()
    used_upgrade: set[int] = set()
    used_targets: set[tuple[str, Any]] = set()

    for annotation in RDDESIGN_RE.finditer(source):
        effect, target_id = _annotated_effect(
            source, key, annotation, variables, base_numbers, upgraded_numbers
        )
        base_index = effect["source"]["baseNumberIndex"]
        localization_index = effect.get("localizationNumberIndex")
        if localization_index is not None:
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()
            localization_path = (
                workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json"
            )
            localization = json.loads(
                localization_path.read_text(encoding="utf-8-sig")
            )
            description = localization.get(
                f"RD_MOD_CARD_{snake}.description"
            )
            localized_numbers = _numbers(
                description, f"{key} localization description"
            )
            if localization_index >= len(localized_numbers):
                raise CardDesignApplyError(
                    f"{key}: localization[{localization_index}] is out of range"
                )
            if localized_numbers[localization_index] != base_numbers[base_index]:
                raise CardDesignApplyError(
                    f"{key}: localization[{localization_index}] value does not "
                    f"match base[{base_index}]"
                )
        upgrade_index = effect["source"].get("upgradeNumberIndex")
        if base_index in used_base:
            raise CardDesignApplyError(f"{key}: duplicate RDDesign base[{base_index}]")
        if upgrade_index is not None and upgrade_index in used_upgrade:
            raise CardDesignApplyError(
                f"{key}: duplicate RDDesign upgrade[{upgrade_index}]"
            )
        if target_id in used_targets:
            raise CardDesignApplyError(
                f"{key}: multiple RDDesign annotations target the same declaration"
            )
        used_base.add(base_index)
        if upgrade_index is not None:
            used_upgrade.add(upgrade_index)
        used_targets.add(target_id)
        effects.append(effect)

    for annotation in RDDESIGN_MANUAL_RE.finditer(source):
        base_index = _checked_index(
            key, "base", annotation.group("base"), base_numbers
        )
        assert base_index is not None
        upgrade_index = _checked_index(
            key, "upgrade", annotation.group("upgrade"), upgraded_numbers
        )
        if base_index in used_base:
            raise CardDesignApplyError(
                f"{key}: duplicate RDDesignManual base[{base_index}]"
            )
        if upgrade_index is not None and upgrade_index in used_upgrade:
            raise CardDesignApplyError(
                f"{key}: duplicate RDDesignManual upgrade[{upgrade_index}]"
            )
        used_base.add(base_index)
        if upgrade_index is not None:
            used_upgrade.add(upgrade_index)
        manual_numbers.append(
            {
                "baseNumberIndex": base_index,
                "upgradeNumberIndex": upgrade_index,
                "reason": annotation.group("reason").strip(),
            }
        )

    for annotation in RDDESIGN_MANUAL_UPGRADE_RE.finditer(source):
        upgrade_index = _checked_index(
            key, "upgrade", annotation.group("upgrade"), upgraded_numbers
        )
        assert upgrade_index is not None
        if upgrade_index in used_upgrade:
            raise CardDesignApplyError(
                f"{key}: duplicate RDDesignManualUpgrade upgrade[{upgrade_index}]"
            )
        used_upgrade.add(upgrade_index)
        manual_numbers.append(
            {
                "upgradeNumberIndex": upgrade_index,
                "reason": annotation.group("reason").strip(),
            }
        )

    effects.sort(key=lambda item: item["source"]["baseNumberIndex"])
    manual_numbers.sort(
        key=lambda item: (
            item.get("baseNumberIndex") is None,
            item.get("baseNumberIndex", -1),
            item.get("upgradeNumberIndex", -1),
        )
    )
    return {
        "constructor": constructor,
        "effects": effects,
        "audit": {
            "manualNumbers": manual_numbers,
            "unmappedBaseNumberIndices": sorted(
                set(range(len(base_numbers))) - used_base
            ),
            "unmappedUpgradeNumberIndices": sorted(
                set(range(len(upgraded_numbers))) - used_upgrade
            ),
        },
    }


def build_mapping_payload(
    workspace: Path,
    cards: list[dict[str, Any]],
    selected: set[str] | None = None,
) -> dict[str, Any]:
    selected = selected or set()
    mappings: dict[str, Any] = {}
    for card in cards:
        key = str(card.get("key") or "")
        if selected and key not in selected:
            continue
        candidate = candidate_for_card(workspace, card)
        if candidate is not None:
            mappings[key] = candidate
    unknown = selected - set(mappings)
    if unknown:
        raise ValueError(f"Registered mapped cards not found: {', '.join(sorted(unknown))}")
    return {"schemaVersion": 1, "cards": mappings}


def write_mapping_file(
    path: Path,
    payload: dict[str, Any],
    merge_keys: set[str] | None = None,
) -> dict[str, Any]:
    result = payload
    if merge_keys:
        existing = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.is_file()
            else {"schemaVersion": 1, "cards": {}}
        )
        existing_cards = existing.get("cards")
        new_cards = payload.get("cards")
        if not isinstance(existing_cards, dict) or not isinstance(new_cards, dict):
            raise ValueError("Mapping payload cards must be objects.")
        merged_cards = dict(existing_cards)
        for key in merge_keys:
            if key not in new_cards:
                raise ValueError(f"Generated mapping is missing selected key: {key}")
            merged_cards[key] = new_cards[key]
        result = {"schemaVersion": 1, "cards": dict(sorted(merged_cards.items()))}

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return result


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    snapshot = args.snapshot.resolve()
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8-sig"))
    cards = snapshot_payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError(f"Snapshot has no cards list: {snapshot}")
    selected = set(args.key)
    payload = build_mapping_payload(workspace, cards, selected)
    if args.write:
        result = write_mapping_file(args.output.resolve(), payload, selected or None)
        print(
            f"CARD_DESIGN_MAPPINGS_REBUILT cards={len(result['cards'])} "
            f"keys={','.join(sorted(selected)) if selected else 'ALL'} "
            f"output={args.output.resolve()}"
        )
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

