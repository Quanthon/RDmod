#!/usr/bin/env python3
"""Refresh and validate the compact effect-reference CSV from official indexes."""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
from pathlib import Path


HEADERS = [
    "效果类别",
    "中文描述模板",
    "内容类型",
    "执行入口 / 触发钩子",
    "核心调用 / 修正方式",
    "官方参考",
    "源码路径",
    "RitsuLib 适配提示",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADERS:
            raise ValueError(f"Unexpected headers in {path}: {reader.fieldnames!r}")
        return list(reader)


def read_index(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["ClassName"]: row for row in csv.DictReader(stream)}


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("\ufeff" + buffer.getvalue(), encoding="utf-8", newline="")
    os.replace(temporary, path)


def main() -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=workspace / "docs" / "卡牌遗物效果代码速查表.csv")
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    rows = read_rows(csv_path)
    indexes = {
        "卡牌": read_index(workspace / "OfficialReference" / "generated" / "CardIndex.csv"),
        "遗物": read_index(workspace / "OfficialReference" / "generated" / "RelicIndex.csv"),
    }
    seen: set[tuple[str, str, str]] = set()
    for row_number, row in enumerate(rows, start=2):
        content_type = row["内容类型"]
        if content_type not in indexes:
            raise ValueError(f"Unsupported 内容类型 on row {row_number}: {content_type}")
        class_name = Path(row["源码路径"]).stem
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name):
            raise ValueError(f"Invalid official class on row {row_number}: {class_name}")
        source = indexes[content_type].get(class_name)
        if source is None:
            raise ValueError(f"Missing {content_type} reference class: {class_name}")
        source_path = source["SourcePath"]
        if not (workspace / Path(source_path)).is_file():
            raise FileNotFoundError(f"Official source not found: {source_path}")
        identity = (content_type, row["中文描述模板"], row["执行入口 / 触发钩子"])
        if identity in seen:
            raise ValueError(f"Duplicate effect identity on row {row_number}: {identity}")
        seen.add(identity)
        row["官方参考"] = f"{source.get('ChineseTitle') or '（缺少中文名）'}（{class_name}）"
        row["源码路径"] = source_path

    write_rows(csv_path, rows)
    print(f"EFFECT_REFERENCE_CSV_OK rows={len(rows)} path={csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
