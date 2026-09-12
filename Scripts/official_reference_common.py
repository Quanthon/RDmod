"""Shared helpers for official source and index maintenance scripts."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from pathlib import Path


def localization_id(name: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    return value.upper()


def plain_chinese(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[/?[^\]]+\]", "", value)).strip()


def normalize_code(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("|", "/")


def unique_matches(text: str, pattern: str, group: str | int = 1) -> list[str]:
    values: list[str] = []
    for match in re.finditer(pattern, text, re.DOTALL):
        value = match.group(group)
        if value and value not in values:
            values.append(value)
    return values


def read_localization(path: Path) -> dict[str, str]:
    if not path.is_file():
        print(f"WARNING: Official Chinese localization not found: {path}")
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {str(key): str(value) for key, value in data.items()}


def relative_source(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_csv(path: Path, headers: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: object) -> str:
    return str(value or "").replace("|", r"\|").replace("\r", " ").replace("\n", " ")
