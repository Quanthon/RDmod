#!/usr/bin/env python3
"""Safely apply mapped card-design field changes to existing card sources."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


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
    "状态": "Status",
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
DEFAULT_TARGETS = {
    "攻击": "AnyEnemy",
    "技能": "Self",
    "能力": "Self",
    "状态": "None",
}
DEFAULT_VAR_NAMES = {
    "DamageVar": "Damage",
    "BlockVar": "Block",
    "CardsVar": "Cards",
    "EnergyVar": "Energy",
    "RepeatVar": "Repeat",
}
POWER_VAR_RECEIVERS = {
    "StrengthPower": "Strength",
    "DexterityPower": "Dexterity",
    "VulnerablePower": "Vulnerable",
    "WeakPower": "Weak",
}
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])-?[0-9]+(?:\.[0-9]+)?(?![A-Za-z0-9_])")


class CardDesignApplyError(ValueError):
    """Raised when an apply cannot be proven safe."""


@dataclass(frozen=True)
class TextEdit:
    start: int
    end: int
    replacement: str
    label: str


@dataclass(frozen=True)
class DynamicVarMatch:
    type_name: str
    ordinal: int
    name: str
    value: Decimal
    value_start: int
    value_end: int
    value_props: str
    declaration_start: int


@dataclass(frozen=True)
class CardApplyResult:
    key: str
    card_path: Path
    card_text: str
    localization_path: Path
    localization_text: str
    changes: tuple[str, ...]


def load_mappings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CardDesignApplyError(f"Card design mapping file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("cards"), dict):
        raise CardDesignApplyError(f"Unsupported card design mapping schema: {path}")
    return payload["cards"]


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise CardDesignApplyError(f"{label} must be numeric; got {value!r}")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise CardDesignApplyError(f"{label} must be numeric; got {value!r}") from exc


def _format_number(value: Decimal, suffix: str = "") -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _numbers(value: Any, field: str) -> list[Decimal]:
    if not isinstance(value, str):
        raise CardDesignApplyError(f"{field} must contain text for numeric synchronization")
    return [Decimal(match.group(0)) for match in NUMBER_RE.finditer(value)]


def _numeric_shape(value: Any, field: str) -> tuple[str, list[Decimal]]:
    if value in {None, ""}:
        return "", []
    if not isinstance(value, str):
        raise CardDesignApplyError(f"{field} must contain text for numeric synchronization")
    return NUMBER_RE.sub("#", value), _numbers(value, field)


def _split_args(text: str, offset: int) -> list[tuple[int, int, str]]:
    parts: list[tuple[int, int, str]] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "([{<":
            depth += 1
        elif character in ")]}>":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append((offset + start, offset + index, text[start:index]))
            start = index + 1
    parts.append((offset + start, offset + len(text), text[start:]))
    return parts


def _constructor_args(source: str, key: str) -> list[tuple[int, int, str]]:
    match = re.search(
        rf"public\s+{re.escape(key)}\s*\(\s*\)\s*:\s*base\s*\((?P<args>[^)]*)\)",
        source,
    )
    if match is None:
        raise CardDesignApplyError(f"{key}: unique constructor base(...) not found")
    return _split_args(match.group("args"), match.start("args"))


def _replace_arg(
    source: str,
    argument: tuple[int, int, str],
    expected: str,
    replacement: str,
    label: str,
) -> TextEdit | None:
    start, end, raw = argument
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    actual = raw.strip()
    if actual != expected:
        raise CardDesignApplyError(
            f"{label}: code has {actual!r}; snapshot expects {expected!r}"
        )
    if expected == replacement:
        return None
    return TextEdit(start + leading, end - trailing, replacement, label)


def _canonical_var_section(source: str, key: str) -> tuple[int, str]:
    match = re.search(
        r"protected\s+override\s+IEnumerable<DynamicVar>\s+CanonicalVars\s*=>\s*"
        r"\[(?P<body>.*?)\]\s*;",
        source,
        re.DOTALL,
    )
    if match is None:
        raise CardDesignApplyError(f"{key}: CanonicalVars collection not found")
    return match.start("body"), match.group("body")


def _dynamic_vars(source: str, key: str) -> list[DynamicVarMatch]:
    section_offset, body = _canonical_var_section(source, key)
    constructor_re = re.compile(
        r"new\s+(?P<type>[A-Za-z_][A-Za-z0-9_]*(?:<[^>]+>)?)\s*"
        r"\((?P<args>[^()]*)\)"
    )
    ordinals: dict[str, int] = {}
    matches: list[DynamicVarMatch] = []
    for constructor in constructor_re.finditer(body):
        type_name = constructor.group("type")
        args_offset = section_offset + constructor.start("args")
        arguments = _split_args(constructor.group("args"), args_offset)
        explicit_name: str | None = None
        value_argument_index = 0
        first = arguments[0][2].strip() if arguments else ""
        if re.fullmatch(r'"[^"\\]*(?:\\.[^"\\]*)*"', first):
            explicit_name = json.loads(first)
            value_argument_index = 1
        if value_argument_index >= len(arguments):
            continue
        value_start, value_end, value_raw = arguments[value_argument_index]
        value_match = re.fullmatch(r"\s*(-?[0-9]+(?:\.[0-9]+)?)([mMdDfF]?)\s*", value_raw)
        if value_match is None:
            continue
        numeric_start = value_start + value_match.start(1)
        numeric_end = value_start + value_match.end(1)
        base_type = type_name.split("<", 1)[0]
        ordinal = ordinals.get(base_type, 0)
        ordinals[base_type] = ordinal + 1
        if explicit_name is not None:
            name = explicit_name
        elif base_type == "PowerVar" and "<" in type_name:
            name = type_name[
                type_name.index("<") + 1 : type_name.rindex(">")
            ].rsplit(".", 1)[-1]
        else:
            name = DEFAULT_VAR_NAMES.get(base_type, base_type.removesuffix("Var"))
        value_props = ",".join(
            argument[2].strip() for argument in arguments[value_argument_index + 1 :]
        )
        matches.append(
            DynamicVarMatch(
                base_type,
                ordinal,
                name,
                Decimal(value_match.group(1)),
                numeric_start,
                numeric_end,
                value_props,
                section_offset + constructor.start(),
            )
        )
    return matches


def _dynamic_target(
    source: str, key: str, target: dict[str, Any], expected_value: Decimal
) -> DynamicVarMatch:
    type_name = str(target.get("type") or "")
    ordinal = target.get("ordinal")
    if not type_name or not isinstance(ordinal, int) or ordinal < 0:
        raise CardDesignApplyError(f"{key}: invalid dynamicVar mapping {target!r}")
    candidates = [item for item in _dynamic_vars(source, key) if item.type_name == type_name]
    if ordinal >= len(candidates):
        raise CardDesignApplyError(
            f"{key}: {type_name}[{ordinal}] not found; found {len(candidates)}"
        )
    match = candidates[ordinal]
    expected_name = target.get("expectedName")
    if expected_name is not None and match.name != expected_name:
        raise CardDesignApplyError(
            f"{key}: {type_name}[{ordinal}] name is {match.name!r}; expected {expected_name!r}"
        )
    expected_props = target.get("expectedValueProps")
    if expected_props is not None:
        actual_props = re.sub(r"\s+", "", match.value_props)
        wanted_props = re.sub(r"\s+", "", str(expected_props))
        if actual_props != wanted_props:
            raise CardDesignApplyError(
                f"{key}: {type_name}[{ordinal}] ValueProp is {match.value_props!r}; "
                f"expected {expected_props!r}"
            )
    if match.value != expected_value:
        raise CardDesignApplyError(
            f"{key}: {type_name}[{ordinal}] code value is {match.value}; "
            f"snapshot expects {expected_value}"
        )
    return match


def _upgrade_pattern(name: str) -> re.Pattern[str]:
    receiver_name = POWER_VAR_RECEIVERS.get(name, name)
    if name in DEFAULT_VAR_NAMES.values():
        receiver = rf"DynamicVars\.{re.escape(receiver_name)}"
    elif name in POWER_VAR_RECEIVERS:
        receiver = (
            rf'(?:DynamicVars\.{re.escape(receiver_name)}|'
            rf'DynamicVars\["{re.escape(name)}"\])'
        )
    else:
        receiver = (
            rf'(?:DynamicVars\.{re.escape(name)}|'
            rf'DynamicVars\["{re.escape(name)}"\])'
        )
    return re.compile(
        rf"(?P<receiver>{receiver})\.UpgradeValueBy\(\s*"
        r"(?P<value>-?[0-9]+(?:\.[0-9]+)?)(?P<suffix>[mM]?)\s*\)\s*;"
    )


def _upgrade_edit(
    source: str,
    key: str,
    name: str,
    old_delta: Decimal,
    new_delta: Decimal,
) -> tuple[TextEdit | None, str | None]:
    pattern = _upgrade_pattern(name)
    matches = list(pattern.finditer(source))
    if len(matches) > 1:
        raise CardDesignApplyError(f"{key}: multiple upgrade statements found for {name}")
    if matches:
        match = matches[0]
        actual = Decimal(match.group("value"))
        if actual != old_delta:
            raise CardDesignApplyError(
                f"{key}: upgrade delta for {name} is {actual}; snapshot expects {old_delta}"
            )
        if actual == new_delta:
            return None, None
        suffix = match.group("suffix") or "m"
        return (
            TextEdit(
                match.start("value"),
                match.end("value"),
                _format_number(new_delta),
                f"{name} upgrade",
            ),
            None,
        )
    if old_delta != 0:
        raise CardDesignApplyError(
            f"{key}: upgrade statement for {name} missing; snapshot delta is {old_delta}"
        )
    if new_delta == 0:
        return None, None
    receiver_name = POWER_VAR_RECEIVERS.get(name, name)
    receiver = (
        f"DynamicVars.{receiver_name}"
        if name in DEFAULT_VAR_NAMES.values() or name in POWER_VAR_RECEIVERS
        else f'DynamicVars["{name}"]'
    )
    return None, f"{receiver}.UpgradeValueBy({_format_number(new_delta, 'm')});"


def _energy_upgrade_edit(
    source: str, key: str, old_delta: Decimal, new_delta: Decimal
) -> tuple[TextEdit | None, str | None]:
    pattern = re.compile(
        r"EnergyCost\.UpgradeBy\(\s*(?P<value>-?[0-9]+)\s*\)\s*;"
    )
    matches = list(pattern.finditer(source))
    if len(matches) > 1:
        raise CardDesignApplyError(f"{key}: multiple EnergyCost upgrade statements found")
    if matches:
        match = matches[0]
        actual = Decimal(match.group("value"))
        if actual != old_delta:
            raise CardDesignApplyError(
                f"{key}: energy upgrade delta is {actual}; snapshot expects {old_delta}"
            )
        if actual == new_delta:
            return None, None
        return (
            TextEdit(
                match.start("value"),
                match.end("value"),
                _format_number(new_delta),
                "upgraded cost",
            ),
            None,
        )
    if old_delta != 0:
        raise CardDesignApplyError(
            f"{key}: EnergyCost upgrade statement missing; snapshot delta is {old_delta}"
        )
    if new_delta == 0:
        return None, None
    return None, f"EnergyCost.UpgradeBy({_format_number(new_delta)});"


def _find_matching_brace(source: str, open_index: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_index, len(source)):
        character = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    raise CardDesignApplyError("Unbalanced C# braces")


def _insert_upgrade_lines(source: str, key: str, lines: Iterable[str]) -> TextEdit | None:
    pending = list(lines)
    if not pending:
        return None
    method = re.search(r"protected\s+override\s+void\s+OnUpgrade\s*\(\s*\)", source)
    rendered = "".join(f"        {line}\n" for line in pending)
    if method is not None:
        tail = source[method.end() :]
        block_offset = tail.find("{")
        arrow_offset = tail.find("=>")
        if block_offset >= 0 and (arrow_offset < 0 or block_offset < arrow_offset):
            open_brace = method.end() + block_offset
            close_brace = _find_matching_brace(source, open_brace)
            return TextEdit(close_brace, close_brace, rendered, "upgrade statements")
        raise CardDesignApplyError(
            f"{key}: cannot add mapped upgrades to expression-bodied OnUpgrade"
        )
    class_match = re.search(rf"public\s+(?:sealed\s+)?class\s+{re.escape(key)}\b", source)
    if class_match is None:
        raise CardDesignApplyError(f"{key}: class declaration not found")
    class_open = source.find("{", class_match.end())
    class_close = _find_matching_brace(source, class_open)
    prefix = "\n    protected override void OnUpgrade()\n    {\n"
    suffix = "    }\n"
    return TextEdit(class_close, class_close, prefix + rendered + suffix, "OnUpgrade")


def _constant_edit(
    source: str, key: str, target: dict[str, Any], old_value: Decimal, new_value: Decimal
) -> TextEdit | None:
    name = str(target.get("name") or "")
    if not name:
        raise CardDesignApplyError(f"{key}: constant mapping requires a name")
    pattern = re.compile(
        rf"\bconst\s+(?:int|decimal|float|double)\s+{re.escape(name)}\s*=\s*"
        r"(?P<value>-?[0-9]+(?:\.[0-9]+)?)(?P<suffix>[mMdDfF]?)\s*;"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise CardDesignApplyError(f"{key}: expected one constant {name}; found {len(matches)}")
    match = matches[0]
    actual = Decimal(match.group("value"))
    if actual != old_value:
        raise CardDesignApplyError(
            f"{key}: constant {name} is {actual}; snapshot expects {old_value}"
        )
    if old_value == new_value:
        return None
    return TextEdit(
        match.start("value"),
        match.end("value"),
        _format_number(new_value),
        f"constant {name}",
    )


def _apply_edits(source: str, edits: Iterable[TextEdit]) -> str:
    ordered = sorted(edits, key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            raise CardDesignApplyError(
                f"Overlapping edits: {previous.label} and {current.label}"
            )
    result = source
    for edit in reversed(ordered):
        result = result[: edit.start] + edit.replacement + result[edit.end :]
    return result


def _mapped_numbers(mapping: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    effects = mapping.get("effects", [])
    if not isinstance(effects, list):
        raise CardDesignApplyError("effects mapping must be an array")
    for effect in effects:
        source = effect.get("source", {})
        base_index = source.get("baseNumberIndex")
        if not isinstance(base_index, int) or base_index < 0 or base_index in result:
            raise CardDesignApplyError(f"Invalid or duplicate baseNumberIndex: {base_index!r}")
        result[base_index] = effect
    return result


def _description_changes(
    key: str, previous: dict[str, Any], current: dict[str, Any], mapping: dict[str, Any]
) -> tuple[list[tuple[dict[str, Any], Decimal, Decimal, Decimal, Decimal]], set[int]]:
    old_shape, old_numbers = _numeric_shape(previous.get("描述"), f"{key} 描述")
    new_shape, new_numbers = _numeric_shape(current.get("描述"), f"{key} 描述")
    old_upgrade_shape, old_upgrade_numbers = _numeric_shape(
        previous.get("升级后描述"), f"{key} 升级后描述"
    )
    new_upgrade_shape, new_upgrade_numbers = _numeric_shape(
        current.get("升级后描述"), f"{key} 升级后描述"
    )
    if old_shape != new_shape or len(old_numbers) != len(new_numbers):
        raise CardDesignApplyError(f"{key}: 描述 contains non-numeric or structural changes")
    if old_upgrade_shape != new_upgrade_shape or len(old_upgrade_numbers) != len(new_upgrade_numbers):
        raise CardDesignApplyError(f"{key}: 升级后描述 contains non-numeric or structural changes")
    changed_indices = {
        index
        for index, (old, new) in enumerate(zip(old_numbers, new_numbers, strict=True))
        if old != new
    }
    changed_upgrade_indices = {
        index
        for index, (old, new) in enumerate(
            zip(old_upgrade_numbers, new_upgrade_numbers, strict=True)
        )
        if old != new
    }
    mapped = _mapped_numbers(mapping)
    covered_base: set[int] = set()
    covered_upgrade: set[int] = set()
    changes: list[tuple[dict[str, Any], Decimal, Decimal, Decimal, Decimal]] = []
    for base_index, effect in mapped.items():
        source = effect["source"]
        upgrade_index = source.get("upgradeNumberIndex")
        if base_index >= len(old_numbers):
            raise CardDesignApplyError(f"{key}: mapped base description number is out of range")
        if upgrade_index is not None and (
            not isinstance(upgrade_index, int)
            or upgrade_index < 0
            or upgrade_index >= len(old_upgrade_numbers)
        ):
            raise CardDesignApplyError(f"{key}: invalid upgradeNumberIndex {upgrade_index!r}")
        upgrade_changed = (
            upgrade_index is not None and upgrade_index in changed_upgrade_indices
        )
        if base_index in changed_indices or upgrade_changed:
            old_upgraded = (
                old_upgrade_numbers[upgrade_index]
                if upgrade_index is not None
                else old_numbers[base_index]
            )
            new_upgraded = (
                new_upgrade_numbers[upgrade_index]
                if upgrade_index is not None
                else new_numbers[base_index]
            )
            changes.append(
                (
                    effect,
                    old_numbers[base_index],
                    new_numbers[base_index],
                    old_upgraded,
                    new_upgraded,
                )
            )
            covered_base.add(base_index)
            if upgrade_index is not None:
                covered_upgrade.add(upgrade_index)
    manual_numbers = mapping.get("audit", {}).get("manualNumbers", [])
    manual_changes = []
    for manual in manual_numbers:
        base_index = manual.get("baseNumberIndex")
        upgrade_index = manual.get("upgradeNumberIndex")
        if base_index in changed_indices or upgrade_index in changed_upgrade_indices:
            manual_changes.append(manual)
    if manual_changes:
        reasons = "; ".join(
            str(item.get("reason") or "manual mapping review required")
            for item in manual_changes
        )
        raise CardDesignApplyError(f"{key}: changed description numbers require manual review: {reasons}")
    missing_base = changed_indices - covered_base
    missing_upgrade = changed_upgrade_indices - covered_upgrade
    if missing_base or missing_upgrade:
        raise CardDesignApplyError(
            f"{key}: changed description numbers lack mappings "
            f"base={sorted(missing_base)} upgrade={sorted(missing_upgrade)}"
        )
    return changes, changed_indices


def _resolve_rarity(card: dict[str, Any], override: str | None = None) -> str:
    raw = card.get("稀有度")
    if raw == "弃用" and override:
        return override
    if card.get("类型") == "状态" and raw in {None, "", "状态"}:
        return "Status"
    if raw in {None, ""} and override:
        return override
    if raw not in RARITY_MAP:
        raise CardDesignApplyError(f"Unsupported 稀有度: {raw!r}")
    return RARITY_MAP[raw]


def _resolve_target(card: dict[str, Any], override: str | None = None) -> str:
    raw = card.get("目标")
    if raw in {None, ""}:
        if override:
            return override
        card_type = card.get("类型")
        if card_type not in DEFAULT_TARGETS:
            raise CardDesignApplyError(f"Unsupported 类型 for default target: {card_type!r}")
        return DEFAULT_TARGETS[card_type]
    if raw not in TARGET_MAP:
        raise CardDesignApplyError(f"Unsupported 目标: {raw!r}")
    return TARGET_MAP[raw]


def _localization_number_edit(
    value: str,
    number_index: int,
    old_value: Decimal,
    new_value: Decimal,
    label: str,
) -> str:
    matches = list(NUMBER_RE.finditer(value))
    if number_index < 0 or number_index >= len(matches):
        raise CardDesignApplyError(f"{label}: localization number index is out of range")
    match = matches[number_index]
    actual = Decimal(match.group(0))
    if actual != old_value:
        raise CardDesignApplyError(
            f"{label}: localization has {actual}; snapshot expects {old_value}"
        )
    return value[: match.start()] + _format_number(new_value) + value[match.end() :]


def plan_card_apply(
    workspace: Path,
    previous: dict[str, Any],
    current: dict[str, Any],
    mapping: dict[str, Any],
    localization: dict[str, Any],
    registration_id: str,
) -> CardApplyResult:
    key = str(current["key"])
    card_path = workspace / "Mod" / "Cards" / f"{key}.cs"
    localization_path = workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json"
    if not card_path.is_file():
        raise CardDesignApplyError(f"{key}: card implementation does not exist")
    with card_path.open("r", encoding="utf-8-sig", newline="") as stream:
        source = stream.read()
    if "[RegisterCard" not in source:
        raise CardDesignApplyError(f"{key}: card implementation is not registered")

    edits: list[TextEdit] = []
    inserted_upgrades: list[str] = []
    labels: list[str] = []
    constructor = _constructor_args(source, key)
    if len(constructor) != 4:
        raise CardDesignApplyError(f"{key}: constructor base(...) must have four arguments")

    old_cost = _decimal(previous.get("费用"), f"{key} 费用")
    new_cost = _decimal(current.get("费用"), f"{key} 费用")
    edit = _replace_arg(source, constructor[0], _format_number(old_cost), _format_number(new_cost), f"{key} cost")
    if edit:
        edits.append(edit)
        labels.append("费用")

    enum_specs = [
        (1, "类型", TYPE_MAP, "CardType"),
        (2, "稀有度", None, "CardRarity"),
        (3, "目标", None, "TargetType"),
    ]
    constructor_mapping = mapping.get("constructor", {})
    if not isinstance(constructor_mapping, dict):
        raise CardDesignApplyError(f"{key}: constructor mapping must be an object")
    for argument_index, field, value_map, enum_type in enum_specs:
        if field == "稀有度":
            rarity_override = constructor_mapping.get("rarity")
            old_value = _resolve_rarity(previous, rarity_override)
            new_value = _resolve_rarity(current, rarity_override)
        elif field == "目标":
            target_override = constructor_mapping.get("target")
            old_value = _resolve_target(previous, target_override)
            new_value = _resolve_target(current, target_override)
        else:
            old_raw = previous.get(field)
            new_raw = current.get(field)
            if old_raw not in value_map or new_raw not in value_map:
                raise CardDesignApplyError(f"{key}: unsupported {field} value")
            old_value = value_map[old_raw]
            new_value = value_map[new_raw]
        edit = _replace_arg(
            source,
            constructor[argument_index],
            f"{enum_type}.{old_value}",
            f"{enum_type}.{new_value}",
            f"{key} {field}",
        )
        if edit:
            edits.append(edit)
            labels.append(field)

    old_upgraded_cost_raw = previous.get("升级后费用")
    new_upgraded_cost_raw = current.get("升级后费用")
    if old_upgraded_cost_raw not in {None, ""} and new_upgraded_cost_raw not in {None, ""}:
        old_upgraded_cost = _decimal(old_upgraded_cost_raw, f"{key} 升级后费用")
        new_upgraded_cost = _decimal(new_upgraded_cost_raw, f"{key} 升级后费用")
        upgrade_edit, insertion = _energy_upgrade_edit(
            source,
            key,
            old_upgraded_cost - old_cost,
            new_upgraded_cost - new_cost,
        )
        if upgrade_edit:
            edits.append(upgrade_edit)
        if insertion:
            inserted_upgrades.append(insertion)
        if old_upgraded_cost != new_upgraded_cost or old_cost != new_cost:
            labels.append("升级后费用")
    elif old_upgraded_cost_raw != new_upgraded_cost_raw:
        raise CardDesignApplyError(f"{key}: adding or removing upgraded cost requires manual review")

    description_fields_changed = any(
        previous.get(field) != current.get(field) for field in ("描述", "升级后描述")
    )
    numeric_changes: list[tuple[dict[str, Any], Decimal, Decimal, Decimal, Decimal]] = []
    if description_fields_changed:
        numeric_changes, _ = _description_changes(key, previous, current, mapping)
    local_copy = dict(localization)
    description_key = f"{registration_id}.description"
    for effect, old_base, new_base, old_upgraded, new_upgraded in numeric_changes:
        target = effect.get("target", {})
        kind = target.get("kind")
        if kind == "dynamicVar":
            match = _dynamic_target(source, key, target, old_base)
            if old_base != new_base:
                edits.append(
                    TextEdit(
                        match.value_start,
                        match.value_end,
                        _format_number(new_base),
                        f"{match.type_name}[{match.ordinal}]",
                    )
                )
            upgrade_edit, insertion = _upgrade_edit(
                source,
                key,
                match.name,
                old_upgraded - old_base,
                new_upgraded - new_base,
            )
            if upgrade_edit:
                edits.append(upgrade_edit)
            if insertion:
                inserted_upgrades.append(insertion)
        elif kind == "constant":
            edit = _constant_edit(source, key, target, old_base, new_base)
            if edit:
                edits.append(edit)
            if old_upgraded != old_base or new_upgraded != new_base:
                raise CardDesignApplyError(
                    f"{key}: constant upgrade changes require a separate explicit mapping"
                )
        else:
            raise CardDesignApplyError(f"{key}: unsupported mapping target kind {kind!r}")
        localization_index = effect.get("localizationNumberIndex")
        if localization_index is not None and old_base != new_base:
            if not isinstance(localization_index, int):
                raise CardDesignApplyError(f"{key}: localizationNumberIndex must be an integer")
            localized = local_copy.get(description_key)
            if not isinstance(localized, str):
                raise CardDesignApplyError(f"{key}: localization key missing: {description_key}")
            local_copy[description_key] = _localization_number_edit(
                localized,
                localization_index,
                old_base,
                new_base,
                f"{key} localization",
            )
        labels.append(f"效果数字[{effect['source']['baseNumberIndex']}]")

    insertion_edit = _insert_upgrade_lines(source, key, inserted_upgrades)
    if insertion_edit:
        edits.append(insertion_edit)
    card_text = _apply_edits(source, edits)

    title_key = f"{registration_id}.title"
    if previous.get("名称") != current.get("名称"):
        if title_key not in local_copy or not isinstance(local_copy[title_key], str):
            raise CardDesignApplyError(f"{key}: localization key missing: {title_key}")
        local_copy[title_key] = str(current.get("名称") or key)
        labels.append("名称")
    localization_text = json.dumps(local_copy, ensure_ascii=False, indent=4) + "\n"
    return CardApplyResult(
        key,
        card_path,
        card_text,
        localization_path,
        localization_text,
        tuple(dict.fromkeys(labels)),
    )


def atomic_write_group(payloads: dict[Path, bytes]) -> None:
    temporaries: dict[Path, Path] = {}
    originals: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            originals[path] = path.read_bytes() if path.exists() else None
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
            temporaries[path] = temporary
        for path, temporary in temporaries.items():
            os.replace(temporary, path)
            replaced.append(path)
        temporaries.clear()
    except Exception:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                descriptor, restore_name = tempfile.mkstemp(
                    prefix=f".{path.name}.", suffix=".restore", dir=path.parent
                )
                restore = Path(restore_name)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(original)
                os.replace(restore, path)
        raise
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)


def apply_cards(results: Iterable[CardApplyResult]) -> None:
    payloads: dict[Path, bytes] = {}
    localization_payload: tuple[Path, str] | None = None
    for result in results:
        payloads[result.card_path] = result.card_text.encode("utf-8")
        if localization_payload is None:
            localization_payload = (result.localization_path, result.localization_text)
        elif localization_payload[1] != result.localization_text:
            raise CardDesignApplyError(
                "Multiple-card apply must share one precomputed localization result"
            )
    if localization_payload is not None:
        payloads[localization_payload[0]] = localization_payload[1].encode("utf-8")
    atomic_write_group(payloads)


