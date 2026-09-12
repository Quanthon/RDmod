#!/usr/bin/env python3
"""Audit RD card wording against official descriptions and project-wide usage."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from sync_card_design import (
    design_diff,
    read_cards,
    read_shared_bytes,
    registration_id,
    target_from_description,
)


DESCRIPTION_FIELDS = {"描述", "升级后描述", "备注"}
NATIVE_KEYWORDS = {"奇巧", "保留", "固有", "消耗", "虚无", "无法打出", "永恒"}
MATCH_THRESHOLD = 0.42
STRONG_MATCH_THRESHOLD = 0.86
MAX_OFFICIAL_CANDIDATES = 5
TARGET_ALIASES = {
    "无": "None",
    "自身": "Self",
    "任意敌人": "AnyEnemy",
    "单个敌人": "AnyEnemy",
    "所有敌人": "AllEnemies",
    "随机敌人": "RandomEnemy",
    "任意玩家": "AnyPlayer",
    "任意队友": "AnyAlly",
    "所有队友": "AllAllies",
    "非生物目标": "TargetedNoCreature",
    "奥斯蒂": "Osty",
}
DEFAULT_TARGETS = {"攻击": "AnyEnemy", "技能": "Self", "能力": "Self", "状态": "None"}

SEMANTIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("damage", re.compile(r"造成.*伤害|失去.*生命")),
    ("block", re.compile(r"获得.*格挡|给予.*格挡")),
    ("draw", re.compile(r"抽.*牌")),
    ("discard", re.compile(r"丢弃")),
    ("exhaust", re.compile(r"消耗")),
    ("retain", re.compile(r"保留")),
    ("energy", re.compile(r"获得.*能量|失去.*能量|耗能")),
    ("hand_add", re.compile(r"加入.*手牌|放入.*手牌")),
    ("pile_move", re.compile(r"抽牌堆|弃牌堆|消耗牌堆")),
    ("power", re.compile(r"力量|敏捷|易伤|虚弱|飞行|蓄力|集中")),
    ("transform", re.compile(r"变化|转化")),
    ("upgrade", re.compile(r"升级")),
)

AMBIGUITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"它们"), "确认代词“它们”的指代在拆句后仍唯一"),
    (re.compile(r"所有牌"), "确认“所有牌”涵盖哪些牌堆、玩家和生成牌"),
    (re.compile(r"随机牌"), "确认随机牌的卡池、类型、颜色和升级状态"),
    (re.compile(r"相同数量|等量"), "确认比较来源与取值时点唯一"),
    (re.compile(r"直到"), "确认终止条件是否包含触发该条件的对象"),
    (re.compile(r"额外"), "确认“额外”的基准值与叠加方式"),
)


@dataclass(frozen=True)
class Clause:
    card_key: str
    title: str
    field: str
    text: str
    target: str


@dataclass(frozen=True)
class OfficialClause:
    class_name: str
    title: str
    text: str
    target: str
    card_type: str
    source_path: str


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
    parser.add_argument(
        "--official-index",
        type=Path,
        default=workspace / "OfficialReference" / "generated" / "CardIndex.csv",
    )
    parser.add_argument(
        "--localization",
        type=Path,
        default=workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json",
    )
    parser.add_argument("--source", choices=("design", "localization", "both"), default="both")
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--key", action="append", default=[])
    parser.add_argument("--show-all", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def split_clauses(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    normalized = value.replace("；", "。").replace("\r", "\n")
    return [
        part.strip()
        for line in normalized.splitlines()
        for part in line.split("。")
        if part.strip()
    ]


def strip_markup(text: str) -> str:
    value = re.sub(r"\[[^\]]+\]", "", text)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\{[^{}]*\}", "X", value)
    return value


def canonical_text(text: str) -> str:
    value = strip_markup(text)
    value = re.sub(r"\d+(?:\.\d+)?|[XＸ]|[一二两三四五六七八九十]+", "#", value)
    value = re.sub(r"[，。；：、！？（）()+＋\s]", "", value)
    return value.lower()


def semantic_signature(text: str, target: str = "") -> tuple[str, ...]:
    plain = strip_markup(text)
    signature = [name for name, pattern in SEMANTIC_PATTERNS if pattern.search(plain)]
    if target:
        signature.append(f"target:{TARGET_ALIASES.get(target, target)}")
    return tuple(sorted(signature))


def mechanism_signature(text: str) -> frozenset[str]:
    plain = strip_markup(text)
    return frozenset(
        name for name, pattern in SEMANTIC_PATTERNS if pattern.search(plain)
    )


def ngram_similarity(left: str, right: str, size: int = 2) -> float:
    def grams(value: str) -> set[str]:
        if len(value) < size:
            return {value} if value else set()
        return {value[index : index + size] for index in range(len(value) - size + 1)}

    left_grams = grams(left)
    right_grams = grams(right)
    if not left_grams or not right_grams:
        return 0.0
    return 2 * len(left_grams & right_grams) / (len(left_grams) + len(right_grams))


def target_similarity(left: str, right: str) -> float:
    left_target = TARGET_ALIASES.get(left, left)
    right_target = TARGET_ALIASES.get(right, right)
    if not left_target or not right_target:
        return 0.5
    return 1.0 if left_target == right_target else 0.0


def semantic_overlap(left: str, right: str) -> float:
    left_signature = mechanism_signature(left)
    right_signature = mechanism_signature(right)
    union = left_signature | right_signature
    if not union:
        return 0.0
    return len(left_signature & right_signature) / len(union)


def similarity(left: Clause, right: OfficialClause | Clause) -> float:
    left_text = canonical_text(left.text)
    right_text = canonical_text(right.text)
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    ngrams = ngram_similarity(left_text, right_text)
    semantics = semantic_overlap(left.text, right.text)
    target = target_similarity(left.target, right.target)
    return 0.55 * sequence + 0.25 * ngrams + 0.15 * semantics + 0.05 * target


def is_strong_semantic_match(
    left: Clause,
    right: OfficialClause | Clause,
) -> bool:
    left_signature = mechanism_signature(left.text)
    right_signature = mechanism_signature(right.text)
    return bool(left_signature) and left_signature == right_signature


def style_issues(text: str, *, check_native_keywords: bool = True) -> list[str]:
    plain = strip_markup(text)
    issues: list[str] = []
    if re.search(r"[(),;]", plain):
        issues.append("玩家可见文本使用半角标点；改用全角标点")
    if re.search(r"\d+点能量", plain):
        issues.append("能量使用文字数字；玩家描述应使用能量图标")
    if "费用" in plain:
        issues.append("官方卡牌通常使用“耗能”，确认是否应统一")
    if check_native_keywords and plain.strip("。") in NATIVE_KEYWORDS:
        issues.append("原生关键词不应作为独立描述句重复显示")
    return issues


def ambiguity_issues(text: str) -> list[str]:
    plain = strip_markup(text)
    return [message for pattern, message in AMBIGUITY_PATTERNS if pattern.search(plain)]


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError(f"Snapshot has no cards list: {path}")
    return cards


def load_official(path: Path) -> list[OfficialClause]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Official card index not found: {path}. Run build_official_card_index.py."
        )
    clauses: list[OfficialClause] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            for text in split_clauses(row.get("ChinesePlainText")):
                clauses.append(
                    OfficialClause(
                        class_name=row.get("ClassName") or "",
                        title=row.get("ChineseTitle") or "",
                        text=text,
                        target=row.get("Target") or "",
                        card_type=row.get("Type") or "",
                        source_path=row.get("SourcePath") or "",
                    )
                )
    return clauses


def resolved_target(card: dict[str, Any]) -> str:
    explicit = str(card.get("目标") or "")
    if explicit:
        return TARGET_ALIASES.get(explicit, explicit)
    inferred = target_from_description(card.get("描述"))
    if inferred:
        return inferred
    return DEFAULT_TARGETS.get(str(card.get("类型") or ""), "")


def card_clauses(cards: Iterable[dict[str, Any]]) -> list[Clause]:
    clauses: list[Clause] = []
    for card in cards:
        key = str(card.get("key") or "")
        title = str(card.get("名称") or key)
        target = resolved_target(card)
        for field in ("描述", "升级后描述"):
            clauses.extend(
                Clause(key, title, field, text, target)
                for text in split_clauses(card.get(field))
            )
    return clauses


def localization_clauses(
    cards: Iterable[dict[str, Any]], localization: dict[str, Any]
) -> list[Clause]:
    clauses: list[Clause] = []
    for card in cards:
        key = str(card.get("key") or "")
        title = str(card.get("名称") or key)
        target = resolved_target(card)
        description = localization.get(f"{registration_id(key)}.description")
        clauses.extend(
            Clause(key, title, "玩家描述", text, target)
            for text in split_clauses(description)
        )
    return clauses


def changed_keys(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> set[str]:
    diff = design_diff(previous, current)
    keys = {item["key"] for item in diff["added"]}
    for item in diff["changed"]:
        if any(change["field"] in DESCRIPTION_FIELDS for change in item["changes"]):
            keys.add(item["key"])
    return keys


def upgrade_consistency_issues(card: dict[str, Any]) -> list[str]:
    base = [
        clause for clause in split_clauses(card.get("描述"))
        if strip_markup(clause).strip("。") not in NATIVE_KEYWORDS
    ]
    upgraded = [
        clause for clause in split_clauses(card.get("升级后描述"))
        if strip_markup(clause).strip("。") not in NATIVE_KEYWORDS
    ]
    if base and not upgraded:
        if card.get("升级后费用") in {None, ""}:
            return []
        return ["升级后费用存在但升级后描述为空，可能忘记同步"]

    issues: list[str] = []
    if len(base) != len(upgraded):
        issues.append(
            f"基础描述有{len(base)}项非关键词效果，升级后有{len(upgraded)}项；确认新增或遗漏是否有意"
        )
    for index, (before, after) in enumerate(zip(base, upgraded), start=1):
        score = SequenceMatcher(None, canonical_text(before), canonical_text(after)).ratio()
        if score < 0.7:
            issues.append(
                f"第{index}项升级前后结构差异较大（{score:.2f}）：{before} → {after}"
            )
    return issues


def audit(
    cards: list[dict[str, Any]],
    official: list[OfficialClause],
    selected_keys: set[str],
    localization: dict[str, Any] | None = None,
    source: str = "design",
) -> dict[str, Any]:
    design = card_clauses(cards)
    localized = localization_clauses(cards, localization or {})
    all_project = design + localized
    selected_pool = {"design": design, "localization": localized, "both": all_project}[source]
    selected = [clause for clause in selected_pool if clause.card_key in selected_keys]
    results: list[dict[str, Any]] = []
    upgrade_checks: list[dict[str, Any]] = []
    counts = {"OFFICIAL_MATCH": 0, "OFFICIAL_CANDIDATE": 0, "AGENT_REVIEW": 0}

    for clause in selected:
        ranked = sorted(
            ((similarity(clause, candidate), candidate) for candidate in official),
            key=lambda item: item[0],
            reverse=True,
        )
        official_matches = [
            item for item in ranked if item[0] >= MATCH_THRESHOLD
        ][:MAX_OFFICIAL_CANDIDATES]
        best_score = official_matches[0][0] if official_matches else 0.0
        best_candidate = official_matches[0][1] if official_matches else None
        if (
            best_score >= STRONG_MATCH_THRESHOLD
            and best_candidate is not None
            and is_strong_semantic_match(clause, best_candidate)
        ):
            status = "OFFICIAL_MATCH"
        elif official_matches:
            status = "OFFICIAL_CANDIDATE"
        else:
            status = "AGENT_REVIEW"
        counts[status] += 1

        project_matches: list[tuple[float, Clause]] = []
        if status == "AGENT_REVIEW":
            project_matches = sorted(
                (
                    (similarity(clause, candidate), candidate)
                    for candidate in all_project
                    if candidate.card_key != clause.card_key
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            project_matches = [item for item in project_matches if item[0] >= 0.45][:3]

        results.append(
            {
                "key": clause.card_key,
                "title": clause.title,
                "field": clause.field,
                "clause": clause.text,
                "status": status,
                "styleIssues": style_issues(
                    clause.text,
                    check_native_keywords=clause.field == "玩家描述",
                ),
                "ambiguityChecks": ambiguity_issues(clause.text),
                "official": [
                    {
                        "score": round(score, 3),
                        "title": candidate.title,
                        "className": candidate.class_name,
                        "clause": candidate.text,
                        "sourcePath": candidate.source_path,
                    }
                    for score, candidate in official_matches
                ],
                "project": [
                    {
                        "score": round(score, 3),
                        "key": candidate.card_key,
                        "title": candidate.title,
                        "clause": candidate.text,
                    }
                    for score, candidate in project_matches
                ],
            }
        )

    for card in cards:
        key = str(card.get("key") or "")
        if key not in selected_keys:
            continue
        issues = upgrade_consistency_issues(card)
        if issues:
            upgrade_checks.append(
                {"key": key, "title": str(card.get("名称") or key), "issues": issues}
            )

    return {
        "summary": {
            "cards": len(selected_keys),
            "clauses": len(results),
            "upgradeReview": len(upgrade_checks),
            **counts,
        },
        "results": results,
        "upgradeChecks": upgrade_checks,
    }


def needs_improvement(item: dict[str, Any]) -> bool:
    best_score = item["official"][0]["score"] if item["official"] else 0.0
    return bool(
        item["status"] != "OFFICIAL_MATCH"
        or best_score < 0.999
        or item["styleIssues"]
        or item["ambiguityChecks"]
    )


def visible_report(report: dict[str, Any], show_all: bool) -> dict[str, Any]:
    if show_all:
        return report
    visible = [item for item in report["results"] if needs_improvement(item)]
    return {
        "summary": {**report["summary"], "reportedClauses": len(visible)},
        "results": visible,
        "upgradeChecks": report["upgradeChecks"],
    }


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        "CARD_DESCRIPTION_AUDIT "
        f"cards={summary['cards']} clauses={summary['clauses']} "
        f"official_match={summary['OFFICIAL_MATCH']} "
        f"official_candidate={summary['OFFICIAL_CANDIDATE']} "
        f"agent_review={summary['AGENT_REVIEW']} "
        f"upgrade_review={summary['upgradeReview']} "
        f"reported={summary.get('reportedClauses', len(report['results']))}"
    )
    for item in report["results"]:
        print(f"[{item['status']}] {item['key']} {item['field']}: {item['clause']}")
        for issue in item["styleIssues"]:
            print(f"  STYLE: {issue}")
        for issue in item["ambiguityChecks"]:
            print(f"  AMBIGUITY: {issue}")
        for candidate in item["official"]:
            print(
                f"  OFFICIAL {candidate['score']:.3f}: "
                f"{candidate['title']} ({candidate['className']}) — {candidate['clause']}"
            )
            print(f"    source: {candidate['sourcePath']}")
        for candidate in item["project"]:
            print(
                f"  PROJECT {candidate['score']:.3f}: "
                f"{candidate['key']} — {candidate['clause']}"
            )
        if item["status"] == "AGENT_REVIEW":
            if not item["official"]:
                print("  OFFICIAL: 无可靠官方相近描述")
            print("  next: Agent确认全局措辞一致性、作用域、时点和歧义后再定稿")
        else:
            print("  next: 打开官方源码与本地化，语义相同时沿用官方措辞")
    for item in report["upgradeChecks"]:
        for issue in item["issues"]:
            print(f"[UPGRADE_REVIEW] {item['key']}: {issue}")


def main() -> int:
    args = parse_args()
    current = read_cards(read_shared_bytes(args.workbook.resolve()))
    previous = load_snapshot(args.snapshot.resolve())
    available_keys = {str(card["key"]) for card in current}
    selected = set(args.key) if args.key else set(available_keys)
    unknown = selected - available_keys
    if unknown:
        raise ValueError(f"Unknown card keys: {', '.join(sorted(unknown))}")
    if args.changed_only:
        selected &= changed_keys(previous, current)
    localization_path = args.localization.resolve()
    localization = (
        json.loads(localization_path.read_text(encoding="utf-8-sig"))
        if localization_path.is_file()
        else {}
    )
    report = audit(
        current,
        load_official(args.official_index.resolve()),
        selected,
        localization,
        args.source,
    )
    report = visible_report(report, args.show_all)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())












