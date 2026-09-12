#!/usr/bin/env python3
"""Build searchable CSV and Markdown indexes for official card sources."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from official_reference_common import (
    localization_id, markdown_cell, normalize_code, plain_chinese,
    read_localization, relative_source, unique_matches, write_csv,
)


HEADERS = ["ClassName", "LocalizationId", "ChineseTitle", "ChineseDescription", "ChinesePlainText", "ChineseSelectionPrompt", "Pools", "Cost", "Type", "Rarity", "Target", "DynamicVars", "Upgrade", "Keywords", "Tags", "Flags", "ImplementationCalls", "SourcePath"]


def main() -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=workspace / "OfficialReference" / "SlayTheSpire2")
    parser.add_argument("--output-dir", type=Path, default=workspace / "OfficialReference" / "generated")
    parser.add_argument("--localization-path", type=Path, default=workspace / "OfficialReference" / "localization" / "zhs" / "cards.json")
    args = parser.parse_args()
    source_root, output_dir, localization_path = args.source_root.resolve(), args.output_dir.resolve(), args.localization_path.resolve()
    cards_dir = source_root / "MegaCrit.Sts2.Core.Models.Cards"
    pools_dir = source_root / "MegaCrit.Sts2.Core.Models.CardPools"
    if not cards_dir.is_dir():
        raise FileNotFoundError(f"Official card source directory not found: {cards_dir}. Run export_official_source.py first.")
    if not pools_dir.is_dir():
        raise FileNotFoundError(f"Official card pool source directory not found: {pools_dir}")

    localization = read_localization(localization_path)
    pool_by_card: dict[str, list[str]] = defaultdict(list)
    for path in pools_dir.glob("*CardPool.cs"):
        pool = path.stem.removesuffix("CardPool")
        for card in re.findall(r"ModelDb\.Card<([A-Za-z_][A-Za-z0-9_]*)>", path.read_text(encoding="utf-8-sig")):
            if pool not in pool_by_card[card]:
                pool_by_card[card].append(pool)

    rows: list[dict[str, str]] = []
    unparsed = 0
    for path in cards_dir.rglob("*.cs"):
        text = path.read_text(encoding="utf-8-sig")
        class_match = re.search(r"public\s+(?:sealed\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*CardModel\b", text)
        if not class_match:
            continue
        class_name = class_match.group(1)
        loc_id = localization_id(class_name)
        constructor = re.search(rf"public\s+{re.escape(class_name)}\s*\(\s*\)\s*:\s*base\s*\(([^)]*)\)", text, re.DOTALL)
        cost = card_type = rarity = target = ""
        if constructor:
            parts = [part.strip() for part in constructor.group(1).split(",")]
            if len(parts) >= 4:
                cost = re.sub(r"m$", "", parts[0])
                card_type = parts[1].removeprefix("CardType.")
                rarity = parts[2].removeprefix("CardRarity.")
                target = parts[3].removeprefix("TargetType.")
        else:
            unparsed += 1
        if re.search(r"HasEnergyCostX\s*=>\s*true", text):
            cost = "X"

        dynamic_vars: list[str] = []
        for match in re.finditer(r"new\s+([A-Za-z_][A-Za-z0-9_]*Var)\s*\(([^\r\n)]*)\)", text):
            value = f"{match.group(1)}({normalize_code(match.group(2))})"
            if value not in dynamic_vars:
                dynamic_vars.append(value)
        upgrade: list[str] = []
        upgrade_match = re.search(r"protected\s+override\s+void\s+OnUpgrade\s*\(\s*\)\s*\{(.*?)\n\s*\}", text, re.DOTALL)
        if upgrade_match:
            body = upgrade_match.group(1)
            for match in re.finditer(r"DynamicVars\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*Upgrade[A-Za-z0-9_]*|UpgradeValueBy)\s*\(([^)]*)\)", body):
                upgrade.append(f"{match.group(1)}.{match.group(2)}({normalize_code(match.group(3))})")
            for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*Upgrade[A-Za-z0-9_]*)\s*\(([^)]*)\)", body):
                value = f"{match.group(1)}({normalize_code(match.group(2))})"
                if not any(item.endswith(value) for item in upgrade):
                    upgrade.append(value)
            if not upgrade:
                upgrade.append(normalize_code(body))
        calls = unique_matches(text, r"([A-Za-z_][A-Za-z0-9_]*(?:Cmd|Command)\.[A-Za-z_][A-Za-z0-9_]*)")
        title, description = localization.get(f"{loc_id}.title", ""), localization.get(f"{loc_id}.description", "")
        flags = [flag for flag in ("GainsBlock", "HasEnergyCostX", "Exhausts", "Ethereal", "Retains") if re.search(rf"(?:override\s+)?bool\s+{flag}\s*=>\s*true", text)]
        rows.append({
            "ClassName": class_name, "LocalizationId": loc_id, "ChineseTitle": title,
            "ChineseDescription": description, "ChinesePlainText": plain_chinese(description),
            "ChineseSelectionPrompt": localization.get(f"{loc_id}.selectionScreenPrompt", ""),
            "Pools": "; ".join(pool_by_card.get(class_name, [])) or "Unassigned", "Cost": cost,
            "Type": card_type, "Rarity": rarity, "Target": target, "DynamicVars": "; ".join(dynamic_vars),
            "Upgrade": "; ".join(upgrade), "Keywords": "; ".join(unique_matches(text, r"CardKeyword\.([A-Za-z_][A-Za-z0-9_]*)")),
            "Tags": "; ".join(unique_matches(text, r"CardTag\.([A-Za-z_][A-Za-z0-9_]*)")), "Flags": "; ".join(flags),
            "ImplementationCalls": "; ".join(calls), "SourcePath": relative_source(path, workspace),
        })
    rows.sort(key=lambda row: (row["Pools"], row["ChineseTitle"], row["ClassName"]))
    if not rows:
        raise RuntimeError(f"No concrete CardModel implementations were indexed from {cards_dir}")
    write_csv(output_dir / "CardIndex.csv", HEADERS, rows)
    md = ["# Official Card Reference Index", "", "Generated from the locally decompiled `sts2.dll` and official Simplified Chinese localization. Regenerate with `scripts/build_official_card_index.py`; do not edit this file manually.", "", "| 中文名 | Class | Pools | Cost | Type | Rarity | Target | 中文效果 | Dynamic vars | Upgrade | Implementation calls | Source |", "|---|---|---|---:|---|---|---|---|---|---|---|---|"]
    for row in rows:
        source = row["SourcePath"].removeprefix("OfficialReference/")
        cells = [row[key] for key in ("ChineseTitle", "ClassName", "Pools", "Cost", "Type", "Rarity", "Target", "ChineseDescription", "DynamicVars", "Upgrade", "ImplementationCalls")]
        md.append("| " + " | ".join(markdown_cell(value) for value in cells) + f" | [source](../{source}) |")
    (output_dir / "CardIndex.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    pool_counts = {pool: sum(row["Pools"] == pool for row in rows) for pool in sorted({row["Pools"] for row in rows})}
    summary = [f"Generated: {datetime.now().isoformat(timespec='seconds')}", f"Source: {source_root}", f"Cards: {len(rows)}", f"Unparsed constructors: {unparsed}", f"Localized titles: {sum(bool(row['ChineseTitle']) for row in rows)}", f"Localized descriptions: {sum(bool(row['ChineseDescription']) for row in rows)}", f"Missing localized titles: {sum(not row['ChineseTitle'] for row in rows)}", f"Localization: {localization_path}", "Pools:"] + [f"  {pool}: {count}" for pool, count in pool_counts.items()]
    (output_dir / "CardIndexSummary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"CARD_INDEX_OK cards={len(rows)} csv={output_dir / 'CardIndex.csv'} markdown={output_dir / 'CardIndex.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
