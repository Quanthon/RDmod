#!/usr/bin/env python3
"""Apply safe mapped card updates without accepting the design snapshot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sync_card_design import design_diff, read_cards, read_shared_bytes


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class KeyUpdateResult:
    key: str
    changes: tuple[str, ...] = ()
    error: str | None = None


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=workspace / "design" / "RD卡牌设计.xlsx",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=workspace / "design" / "card-design-snapshots" / "current.json",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def orchestrate(
    diff: dict[str, Any],
    apply_key: Callable[[str], KeyUpdateResult],
) -> dict[str, Any]:
    applied: list[dict[str, Any]] = []
    manual: list[dict[str, str]] = []

    for item in diff["added"]:
        manual.append({"key": item["key"], "reason": "新增卡牌需要实现，不能自动更新"})
    for item in diff["removed"]:
        manual.append({"key": item["key"], "reason": "删除项只报告，不自动删除"})

    for item in diff["changed"]:
        result = apply_key(str(item["key"]))
        if result.error:
            manual.append({"key": result.key, "reason": result.error})
        else:
            applied.append({"key": result.key, "changes": list(result.changes)})

    total_changes = sum(diff["summary"][name] for name in ("added", "removed", "changed"))
    snapshot_message = ""
    if total_changes > 0 and not manual:
        snapshot_message = "自动修改已完成；请在编译和验证后手工接受快照"
        manual.append({"key": "<snapshot>", "reason": snapshot_message})

    return {
        "summary": {
            "total": total_changes,
            "autoUpdated": len(applied),
            "manualRequired": len(manual),
            "snapshotUpdated": False,
        },
        "autoUpdated": applied,
        "manualRequired": manual,
        "snapshotMessage": snapshot_message,
    }


def run_json_command(command: list[str], workspace: Path) -> tuple[int, Any, str]:
    completed = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout.strip()
    payload: Any = None
    if output:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            payload = None
    error = completed.stderr.strip() or output
    return completed.returncode, payload, error


def load_diff(workbook: Path, snapshot: Path) -> dict[str, Any]:
    if not snapshot.is_file():
        raise FileNotFoundError(
            f"Card design snapshot not found: {snapshot}. Create a verified baseline first."
        )
    previous = json.loads(snapshot.read_text(encoding="utf-8-sig"))
    current = read_cards(read_shared_bytes(workbook))
    return design_diff(previous.get("cards", []), current)


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        "AUTO_CARD_UPDATE_RESULT "
        f"total={summary['total']} auto_updated={summary['autoUpdated']} "
        f"manual_required={summary['manualRequired']} "
        f"snapshot_updated={str(summary['snapshotUpdated']).lower()}"
    )
    if summary["total"] == 0:
        print("[NO_CHANGES] 工作簿与快照一致，无需更新。")
    for item in report["autoUpdated"]:
        changes = ", ".join(item["changes"]) or "已通过映射校验，无代码改动"
        print(f"[AUTO_UPDATED] {item['key']}: {changes}")
    for item in report["manualRequired"]:
        print(f"[MANUAL_REQUIRED] {item['key']}: {item['reason']}")
    if summary["snapshotUpdated"]:
        print("[SNAPSHOT_UPDATED] 全部变化均已自动处理，快照与数字映射已更新。")
    elif summary["total"] > 0:
        print("[SNAPSHOT_UNCHANGED] 存在不能自动处理的变化，快照未更新。")


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    workbook = args.workbook.resolve()
    snapshot = args.snapshot.resolve()
    sync_script = Path(__file__).resolve().parent / "sync_card_design.py"
    diff = load_diff(workbook, snapshot)

    def apply_key(key: str) -> KeyUpdateResult:
        code, payload, error = run_json_command(
            [
                sys.executable,
                str(sync_script),
                "--workbook",
                str(workbook),
                "--snapshot",
                str(snapshot),
                "--apply",
                "--key",
                key,
                "--as-json",
            ],
            workspace,
        )
        if code == 0 and isinstance(payload, dict):
            applied = payload.get("applied") or []
            if applied:
                return KeyUpdateResult(key, tuple(applied[0].get("changes") or ()))
            return KeyUpdateResult(key)
        if isinstance(payload, dict) and payload.get("manualRequired"):
            reason = str(payload["manualRequired"][0].get("error") or "需要人工处理")
        else:
            reason = error or f"同步器退出码 {code}"
        return KeyUpdateResult(key, error=reason)

    report = orchestrate(diff, apply_key)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if report["summary"]["manualRequired"] == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AUTO_CARD_UPDATE_ERROR {exc}", file=sys.stderr)
        raise SystemExit(1)
