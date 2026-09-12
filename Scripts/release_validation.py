"""Read-only localization checks shared by release and local debugging."""
from __future__ import annotations

import json
import re
from pathlib import Path

NATIVE_KEYWORD_TEXT = {
    "Sly": "奇巧",
    "Retain": "保留",
    "Innate": "固有",
    "Exhaust": "消耗",
    "Ethereal": "虚无",
    "Unplayable": "无法打出",
    "Eternal": "永恒",
}


def validate_localization_json(localization_root: Path) -> int:
    paths = sorted(localization_root.rglob("*.json"))
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            relative = path.relative_to(localization_root)
            raise ValueError(
                f"Invalid localization JSON: {relative}:{exc.lineno}:{exc.colno}: {exc.msg}"
            ) from exc
    return len(paths)


def _registration_id(key: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake)
    return f"RD_MOD_CARD_{snake.upper()}"


def _native_keywords(source: str) -> set[str]:
    keywords: set[str] = set()
    canonical = re.search(
        r"CanonicalKeywords\s*=>\s*(.*?);",
        source,
        re.DOTALL,
    )
    if canonical:
        keywords.update(re.findall(r"CardKeyword\.([A-Za-z]+)", canonical.group(1)))
    keywords.update(re.findall(r"AddKeyword\(CardKeyword\.([A-Za-z]+)\)", source))
    return keywords


def _standalone_sentences(description: str) -> set[str]:
    without_tags = re.sub(r"\[[^\]]+\]", "", description)
    return {
        part.strip()
        for part in re.split(r"[。；\r\n]+", without_tags)
        if part.strip()
    }


def validate_native_keyword_localization(cards_dir: Path, cards_json: Path) -> int:
    localization = json.loads(cards_json.read_text(encoding="utf-8-sig"))
    if not isinstance(localization, dict):
        raise ValueError(f"Localization root must be an object: {cards_json}")

    checked = 0
    duplicates: list[str] = []
    for card_path in sorted(cards_dir.glob("*.cs")):
        source = card_path.read_text(encoding="utf-8-sig")
        if "[RegisterCard" not in source:
            continue
        checked += 1
        description = localization.get(
            f"{_registration_id(card_path.stem)}.description"
        )
        if not isinstance(description, str):
            continue
        sentences = _standalone_sentences(description)
        for keyword in sorted(_native_keywords(source)):
            native_text = NATIVE_KEYWORD_TEXT.get(keyword)
            if native_text and native_text in sentences:
                duplicates.append(f"{card_path.stem}: {keyword} ({native_text})")
    if duplicates:
        raise ValueError(
            "Native card keywords must not be repeated as standalone localization "
            "sentences; the game appends them automatically:\n"
            + "\n".join(duplicates)
        )
    return checked

