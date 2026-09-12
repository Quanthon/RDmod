#!/usr/bin/env python3
"""Compare RD card design workbook data with the last accepted JSON snapshot."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import posixpath
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

SHEET_NAME = "卡牌"
WORKBOOK_HEADERS = [
    "key",
    "名称",
    "稀有度",
    "类型",
    "费用",
    "描述",
    "升级后费用",
    "升级后描述",
    "备注",
]
# 快照继续保留“目标”作为派生字段，供差异、脚手架和自动应用统一使用。
HEADERS = [*WORKBOOK_HEADERS[:-1], "目标", "备注"]
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": MAIN_NS, "r": REL_NS, "p": PACKAGE_REL_NS}
PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
NOTE_TARGET_RE = re.compile(r"^\s*目标\s*[:：]\s*(.*?)\s*$")
RANDOM_ENEMY_RE = re.compile(r"随机(?:对)?(?:一名|一个)?敌人")
DEFAULT_TARGET_INPUTS = {
    "攻击": {None, "", "任意敌人", "单个敌人", "AnyEnemy"},
    "技能": {None, "", "自身", "Self"},
    "能力": {None, "", "自身", "Self"},
    "状态": {None, "", "无", "None"},
}
SUPPORTED_TARGET_INPUTS = {
    "无", "None", "自身", "Self", "任意敌人", "单个敌人", "AnyEnemy",
    "所有敌人", "AllEnemies", "随机敌人", "RandomEnemy", "任意玩家", "AnyPlayer",
    "任意队友", "AnyAlly", "所有队友", "AllAllies", "非生物目标",
    "TargetedNoCreature", "奥斯蒂", "Osty", "待确认", "不确定", "?", "TODO",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Compare RD卡牌设计.xlsx with the last accepted card-design JSON snapshot."
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=workspace / "design" / "RD卡牌设计.xlsx",
        help="Card design workbook path.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=workspace / "design" / "card-design-snapshots" / "current.json",
        help="Accepted baseline snapshot path.",
    )
    parser.add_argument(
        "--history-dir",
        type=Path,
        default=None,
        help="Snapshot history directory; defaults to <snapshot-dir>/history.",
    )
    parser.add_argument(
        "--accept",
        action="store_true",
        help="Accept the current workbook after code changes are complete.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Safely apply mapped small changes to existing card code and localization.",
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=workspace / "design" / "card-design-mappings.json",
        help="Card design-to-code mapping file.",
    )
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        help="Limit comparison or acceptance to this PascalCase card key; repeatable.",
    )
    parser.add_argument(
        "--as-json",
        action="store_true",
        help="Print the comparison result as machine-readable JSON.",
    )
    return parser.parse_args()


def open_shared_read(path: Path) -> BinaryIO:
    """Open a saved workbook even while Excel keeps it open."""
    if os.name != "nt":
        return path.open("rb")

    import msvcrt

    invalid_handle = ctypes.c_void_p(-1).value
    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080,
        None,
    )
    if handle == invalid_handle:
        raise ctypes.WinError()
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except Exception:
        ctypes.windll.kernel32.CloseHandle(handle)
        raise
    return os.fdopen(descriptor, "rb")


def read_shared_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"Card design workbook not found: {path}")
    with open_shared_read(path) as stream:
        return stream.read()


def xml_from_zip(archive: zipfile.ZipFile, entry: str) -> ET.Element:
    try:
        return ET.fromstring(archive.read(entry))
    except KeyError as exc:
        raise ValueError(f"Workbook entry not found: {entry}") from exc


def worksheet_entry(archive: zipfile.ZipFile, name: str) -> str:
    workbook = xml_from_zip(archive, "xl/workbook.xml")
    relationships = xml_from_zip(archive, "xl/_rels/workbook.xml.rels")
    sheet = next(
        (node for node in workbook.findall(".//x:sheet", NS) if node.get("name") == name),
        None,
    )
    if sheet is None:
        raise ValueError(f"Worksheet '{name}' not found.")
    relationship_id = sheet.get(f"{{{REL_NS}}}id")
    relationship = next(
        (
            node
            for node in relationships.findall(".//p:Relationship", NS)
            if node.get("Id") == relationship_id
        ),
        None,
    )
    if relationship is None:
        raise ValueError(f"Worksheet relationship '{relationship_id}' not found.")
    target = (relationship.get("Target") or "").replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = xml_from_zip(archive, "xl/sharedStrings.xml")
    return [
        "".join(node.text or "" for node in item.findall(".//x:t", NS))
        for item in root.findall("x:si", NS)
    ]


def column_index(reference: str) -> int:
    match = re.match(r"^[A-Z]+", reference)
    if not match:
        raise ValueError(f"Invalid cell reference: {reference}")
    index = 0
    for character in match.group(0):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def numeric_value(raw: str) -> int | float | str:
    try:
        number = float(raw)
    except ValueError:
        return raw
    return int(number) if number.is_integer() else number


def cell_value(cell: ET.Element, strings: list[str]) -> Any:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall("x:is//x:t", NS))
    value = cell.find("x:v", NS)
    if value is None or value.text is None:
        return None
    raw = value.text
    if cell_type == "s":
        index = int(raw)
        if index < 0 or index >= len(strings):
            raise ValueError(f"Shared string index out of range: {index}")
        return strings[index]
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e"}:
        return raw
    return numeric_value(raw)


def read_cards(workbook_bytes: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as archive:
        strings = shared_strings(archive)
        sheet = xml_from_zip(archive, worksheet_entry(archive, SHEET_NAME))
        matrix: list[list[Any]] = []
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            values: list[Any] = [None] * len(WORKBOOK_HEADERS)
            for cell in row.findall("x:c", NS):
                index = column_index(cell.get("r") or "")
                if 0 <= index < len(values):
                    values[index] = cell_value(cell, strings)
            matrix.append(values)

    if not matrix:
        raise ValueError(f"Worksheet '{SHEET_NAME}' has no rows.")
    actual_headers = ["" if value is None else str(value) for value in matrix[0]]
    if actual_headers != WORKBOOK_HEADERS:
        raise ValueError(
            f"Unexpected headers: {actual_headers!r}; expected {WORKBOOK_HEADERS!r}."
        )

    cards: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row_number, values in enumerate(matrix[1:], start=2):
        key = "" if values[0] is None else str(values[0]).strip()
        if not key:
            continue
        if not PASCAL_CASE.fullmatch(key):
            raise ValueError(f"Card key '{key}' on worksheet row {row_number} is not PascalCase.")
        if key in seen:
            raise ValueError(
                f"Duplicate card key '{key}' on worksheet rows {seen[key]} and {row_number}."
            )
        seen[key] = row_number
        card = dict(zip(WORKBOOK_HEADERS, values, strict=True))
        card["目标"] = target_from_note(card.get("备注"), row_number=row_number)
        card = {field: card.get(field) for field in HEADERS}
        cards.append(card)
    return sorted(cards, key=lambda card: str(card["key"]))


def target_from_note(note: Any, *, row_number: int | None = None) -> str | None:
    """Extract one explicit `目标：...` declaration from a card note."""
    declarations: list[str] = []
    for line in str(note or "").splitlines():
        match = NOTE_TARGET_RE.fullmatch(line)
        if match is None:
            continue
        value = match.group(1).strip()
        if not value:
            location = f" on worksheet row {row_number}" if row_number else ""
            raise ValueError(f"Empty target declaration{location}; use 目标：<目标>.")
        declarations.append(value)
    if len(declarations) > 1:
        location = f" on worksheet row {row_number}" if row_number else ""
        raise ValueError(f"Multiple target declarations{location}; keep exactly one 目标： line.")
    if declarations and declarations[0] not in SUPPORTED_TARGET_INPUTS:
        location = f" on worksheet row {row_number}" if row_number else ""
        raise ValueError(f"Unsupported target declaration {declarations[0]!r}{location}.")
    return declarations[0] if declarations else None


def target_from_description(description: Any) -> str | None:
    """Infer a special play target from unambiguous player-facing wording."""
    text = str(description or "")
    if RANDOM_ENEMY_RE.search(text) or "随机对敌人" in text:
        return "RandomEnemy"
    if "所有敌人" in text:
        return "AllEnemies"
    if "所有玩家" in text or "所有队友" in text:
        return "AllAllies"
    if "另一名玩家" in text or "另一位玩家" in text:
        return "AnyAlly"
    return None


def registration_id(key: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake)
    return f"RD_MOD_CARD_{snake.upper()}"


def affected_files(key: str, fields: list[str] | None = None) -> list[str]:
    fields = fields or []
    files: list[str] = []
    if not fields or any(field != "名称" for field in fields):
        files.append(f"Mod/Cards/{key}.cs")
    if not fields or any(
        field in {"名称", "描述", "升级后描述", "备注"} for field in fields
    ):
        files.append("Mod/RDMod/localization/zhs/cards.json")
    return files


def design_diff(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> dict[str, Any]:
    old = {str(card["key"]): card for card in previous}
    new = {str(card["key"]): card for card in current}
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for key in sorted(new):
        card = new[key]
        if key not in old:
            added.append(
                {
                    "key": key,
                    "name": card.get("名称"),
                    "registrationId": registration_id(key),
                    "files": affected_files(key),
                }
            )
            continue
        changes = []
        for field in HEADERS[1:]:
            before = old[key].get(field)
            after = card.get(field)
            if field == "目标":
                before = semantic_target_input(old[key])
                after = semantic_target_input(card)
            if before != after:
                changes.append({"field": field, "before": before, "after": after})
        if changes:
            changed.append(
                {
                    "key": key,
                    "name": card.get("名称"),
                    "registrationId": registration_id(key),
                    "changes": changes,
                    "files": affected_files(key, [change["field"] for change in changes]),
                }
            )

    for key in sorted(old):
        if key not in new:
            card = old[key]
            removed.append(
                {
                    "key": key,
                    "name": card.get("名称"),
                    "registrationId": registration_id(key),
                    "files": affected_files(key),
                }
            )

    possible_renames = [
        {"fromKey": old_card["key"], "toKey": new_card["key"], "name": old_card["name"]}
        for old_card in removed
        for new_card in added
        if old_card.get("name") and old_card.get("name") == new_card.get("name")
    ]
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "possibleRenames": possible_renames,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "possibleRenames": len(possible_renames),
        },
    }


def semantic_target_input(card: dict[str, Any]) -> Any:
    """Treat an omitted target and an explicitly written type default as equivalent."""
    value = card.get("目标")
    defaults = DEFAULT_TARGET_INPUTS.get(str(card.get("类型") or ""), {None, ""})
    return None if value in defaults else value


def filter_diff(diff: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    if not keys:
        return diff
    filtered = {
        "added": [card for card in diff["added"] if card["key"] in keys],
        "removed": [card for card in diff["removed"] if card["key"] in keys],
        "changed": [card for card in diff["changed"] if card["key"] in keys],
        "possibleRenames": [
            rename
            for rename in diff["possibleRenames"]
            if rename["fromKey"] in keys or rename["toKey"] in keys
        ],
    }
    filtered["summary"] = {
        "added": len(filtered["added"]),
        "removed": len(filtered["removed"]),
        "changed": len(filtered["changed"]),
        "possibleRenames": len(filtered["possibleRenames"]),
    }
    return filtered


def merge_selected_cards(
    previous: list[dict[str, Any]], current: list[dict[str, Any]], keys: set[str]
) -> list[dict[str, Any]]:
    merged = {str(card["key"]): card for card in previous}
    current_by_key = {str(card["key"]): card for card in current}
    for key in keys:
        if key in current_by_key:
            merged[key] = current_by_key[key]
        else:
            merged.pop(key, None)
    return [merged[key] for key in sorted(merged)]


def print_human_diff(diff: dict[str, Any]) -> None:
    summary = diff["summary"]
    print(
        "CARD_DESIGN_DIFF "
        f"added={summary['added']} removed={summary['removed']} "
        f"changed={summary['changed']} possible_renames={summary['possibleRenames']}"
    )
    for card in diff["added"]:
        print(f"[ADDED] {card['key']} ({card['name']}) id={card['registrationId']}")
        print(f"  files: {', '.join(card['files'])}")
    for card in diff["removed"]:
        print(
            f"[REMOVED] {card['key']} ({card['name']}) id={card['registrationId']} "
            "-- report only; do not delete without confirmation"
        )
        print(f"  files: {', '.join(card['files'])}")
    for card in diff["changed"]:
        print(f"[CHANGED] {card['key']} ({card['name']}) id={card['registrationId']}")
        for change in card["changes"]:
            before = json.dumps(change["before"], ensure_ascii=False, separators=(",", ":"))
            after = json.dumps(change["after"], ensure_ascii=False, separators=(",", ":"))
            print(f"  {change['field']}: {before} -> {after}")
        print(f"  files: {', '.join(card['files'])}")
    for rename in diff["possibleRenames"]:
        print(
            f"[POSSIBLE_RENAME] {rename['fromKey']} -> {rename['toKey']} ({rename['name']}); "
            "confirm registration/save compatibility before editing"
        )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def relative_workbook_path(workbook: Path, workspace: Path) -> str:
    try:
        return workbook.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return workbook.resolve().as_posix()


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    workbook = args.workbook.resolve()
    snapshot = args.snapshot.resolve()
    history_dir = (args.history_dir or snapshot.parent / "history").resolve()
    selected_keys = set(args.key)
    if args.accept and args.apply:
        raise ValueError("--accept and --apply cannot be used together.")
    invalid_keys = sorted(key for key in selected_keys if not PASCAL_CASE.fullmatch(key))
    if invalid_keys:
        raise ValueError(f"--key values must be PascalCase: {', '.join(invalid_keys)}")

    workbook_bytes = read_shared_bytes(workbook)
    cards = read_cards(workbook_bytes)
    workbook_hash = hashlib.sha256(workbook_bytes).hexdigest().upper()
    current_snapshot = {
        "schemaVersion": 1,
        "capturedAtUtc": datetime.now(timezone.utc).isoformat(),
        "workbook": relative_workbook_path(workbook, workspace),
        "workbookSha256": workbook_hash,
        "sheet": SHEET_NAME,
        "keyColumn": "key",
        "columns": HEADERS,
        "cards": cards,
    }

    previous_snapshot: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    if snapshot.is_file():
        previous_snapshot = json.loads(snapshot.read_text(encoding="utf-8-sig"))
        if previous_snapshot.get("schemaVersion") != 1:
            raise ValueError(
                f"Unsupported snapshot schema version: {previous_snapshot.get('schemaVersion')}"
            )
        full_diff = design_diff(previous_snapshot.get("cards", []), cards)
        known_keys = {
            str(card["key"])
            for card in previous_snapshot.get("cards", []) + cards
        }
        unknown_keys = sorted(selected_keys - known_keys)
        if unknown_keys:
            raise ValueError(f"Card key not found in workbook or snapshot: {', '.join(unknown_keys)}")
        diff = filter_diff(full_diff, selected_keys)

    if args.accept:
        if diff and all(
            diff["summary"][name] == 0 for name in ("added", "removed", "changed")
        ):
            from build_card_design_mappings import (
                build_mapping_payload,
                write_mapping_file,
            )

            unchanged_snapshot = previous_snapshot or current_snapshot
            mapping_payload = build_mapping_payload(
                workspace, unchanged_snapshot["cards"], selected_keys
            )
            rebuilt_mappings = write_mapping_file(
                args.mappings.resolve(),
                mapping_payload,
                selected_keys or None,
            )
            print(
                f"CARD_DESIGN_MAPPINGS_REBUILT cards={len(rebuilt_mappings['cards'])} "
                f"keys={','.join(sorted(selected_keys)) if selected_keys else 'ALL'} "
                f"output={args.mappings.resolve()}"
            )
            print(f"CARD_DESIGN_SNAPSHOT_UNCHANGED cards={len(cards)} snapshot={snapshot}")
            return 0
        accepted_snapshot = current_snapshot
        if selected_keys:
            accepted_snapshot = dict(current_snapshot)
            accepted_snapshot["cards"] = merge_selected_cards(
                previous_snapshot.get("cards", []) if previous_snapshot else [],
                cards,
                selected_keys,
            )
            accepted_snapshot["partialAccept"] = {
                "keys": sorted(selected_keys),
                "sourceWorkbookSha256": workbook_hash,
            }
            accepted_snapshot["workbookSha256"] = None
        from build_card_design_mappings import (
            build_mapping_payload,
            write_mapping_file,
        )

        mapping_payload = build_mapping_payload(
            workspace, accepted_snapshot["cards"], selected_keys
        )
        write_json(snapshot, accepted_snapshot)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        history_path = history_dir / f"{timestamp}_{workbook_hash[:8].lower()}.json"
        write_json(history_path, accepted_snapshot)
        rebuilt_mappings = write_mapping_file(
            args.mappings.resolve(),
            mapping_payload,
            selected_keys or None,
        )
        print(
            f"CARD_DESIGN_MAPPINGS_REBUILT cards={len(rebuilt_mappings['cards'])} "
            f"keys={','.join(sorted(selected_keys)) if selected_keys else 'ALL'} "
            f"output={args.mappings.resolve()}"
        )
        print(
            f"CARD_DESIGN_SNAPSHOT_ACCEPTED cards={len(accepted_snapshot['cards'])} "
            f"keys={','.join(sorted(selected_keys)) if selected_keys else 'ALL'} "
            f"snapshot={snapshot} history={history_path}"
        )
        return 0

    if args.apply:
        if previous_snapshot is None or diff is None:
            raise FileNotFoundError(
                f"Card design snapshot not found: {snapshot}. "
                "Create and verify the baseline before applying changes."
            )
        from dataclasses import replace

        from card_design_apply import (
            CardDesignApplyError,
            apply_cards,
            load_mappings,
            plan_card_apply,
        )

        if diff["added"] or diff["removed"]:
            raise CardDesignApplyError(
                "--apply only supports changed existing cards; additions and removals "
                "require the normal manual workflow."
            )
        mappings = load_mappings(args.mappings.resolve())
        previous_cards = {
            str(card["key"]): card for card in previous_snapshot.get("cards", [])
        }
        current_cards = {str(card["key"]): card for card in cards}
        localization_path = (
            workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json"
        )
        with localization_path.open("r", encoding="utf-8-sig", newline="") as stream:
            localization_source = stream.read()
        localization_newline = "\r\n" if "\r\n" in localization_source else "\n"
        localization = json.loads(localization_source)
        if not isinstance(localization, dict):
            raise CardDesignApplyError(
                f"Localization root must be an object: {localization_path}"
            )
        plans = []
        failures: list[dict[str, str]] = []
        for changed_card in diff["changed"]:
            key = str(changed_card["key"])
            mapping = mappings.get(key)
            if not isinstance(mapping, dict):
                failures.append({"key": key, "error": "mapping entry is missing"})
                continue
            changed_fields = {change["field"] for change in changed_card["changes"]}
            if "备注" in changed_fields:
                failures.append(
                    {
                        "key": key,
                        "error": (
                            "备注变化需要人工审查动态变量、战斗中补充文本和目标语义"
                        ),
                    }
                )
                continue
            unsupported_fields = changed_fields - {
                "名称",
                "类型",
                "稀有度",
                "费用",
                "升级后费用",
                "描述",
                "升级后描述",
                "目标",
                "备注",
            }
            if unsupported_fields:
                failures.append(
                    {
                        "key": key,
                        "error": "unsupported fields: " + ", ".join(sorted(unsupported_fields)),
                    }
                )
                continue
            try:
                plan = plan_card_apply(
                    workspace,
                    previous_cards[key],
                    current_cards[key],
                    mapping,
                    localization,
                    registration_id(key),
                )
            except CardDesignApplyError as exc:
                failures.append({"key": key, "error": str(exc)})
                continue
            localization = json.loads(plan.localization_text)
            plans.append(plan)

        if plans:
            final_localization_text = json.dumps(
                localization, ensure_ascii=False, indent=4
            ) + "\n"
            if localization_newline == "\r\n":
                final_localization_text = final_localization_text.replace(
                    "\n", localization_newline
                )
            plans = [
                replace(plan, localization_text=final_localization_text) for plan in plans
            ]
            apply_cards(plans)

        report = {
            "applied": [
                {"key": plan.key, "changes": list(plan.changes)} for plan in plans
            ],
            "manualRequired": failures,
        }
        if args.as_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(
                f"CARD_DESIGN_APPLY applied={len(plans)} "
                f"manual_required={len(failures)}"
            )
            for plan in plans:
                print(f"[APPLIED] {plan.key}: {', '.join(plan.changes) or 'no code changes'}")
            for failure in failures:
                print(f"[MANUAL_REQUIRED] {failure['key']}: {failure['error']}")
            if plans:
                print("  next: run debug_after_code.py, then --accept for verified keys")
        return 2 if failures else 0

    if previous_snapshot is None or diff is None:
        raise FileNotFoundError(
            f"Card design snapshot not found: {snapshot}. "
            "Run once with --accept after confirming the current code matches the workbook."
        )

    if args.as_json:
        print(
            json.dumps(
                {
                    "workbook": relative_workbook_path(workbook, workspace),
                    "snapshot": snapshot.as_posix(),
                    "diff": diff,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_human_diff(diff)
        if all(diff["summary"][name] == 0 for name in ("added", "removed", "changed")):
            print(f"CARD_DESIGN_NO_CHANGES cards={len(cards)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CARD_DESIGN_ERROR {exc}", file=sys.stderr)
        raise SystemExit(1)
