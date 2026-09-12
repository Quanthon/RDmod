from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from audit_card_descriptions import (  # noqa: E402
    Clause,
    OfficialClause,
    audit,
    changed_keys,
    needs_improvement,
    style_issues,
    upgrade_consistency_issues,
    visible_report,
)


def design_card(key: str, description: str, note: str | None = None) -> dict[str, object]:
    return {
        "key": key,
        "名称": key,
        "稀有度": "普通",
        "类型": "攻击",
        "费用": 1,
        "描述": description,
        "升级后费用": 1,
        "升级后描述": description,
        "目标": "任意敌人",
        "备注": note,
    }


class AuditCardDescriptionsTests(unittest.TestCase):
    def test_matches_official_wording_with_normalized_target(self) -> None:
        cards = [design_card("TestCard", "造成8点伤害。")]
        official = [
            OfficialClause(
                "StrikeIronclad",
                "打击",
                "造成{Damage:diff()}点伤害",
                "AnyEnemy",
                "Attack",
                "OfficialReference/StrikeIronclad.cs",
            )
        ]

        report = audit(cards, official, {"TestCard"})

        self.assertEqual(report["summary"]["OFFICIAL_MATCH"], 2)
        self.assertTrue(all(item["official"] for item in report["results"]))
        self.assertFalse(any(needs_improvement(item) for item in report["results"]))
        self.assertEqual(visible_report(report, False)["results"], [])

    def test_without_official_match_requires_agent_review(self) -> None:
        cards = [
            design_card("FirstCard", "它们获得保留。"),
            design_card("SecondCard", "你的苹果酒获得保留。"),
        ]

        report = audit(cards, [], {"FirstCard"})

        item = report["results"][0]
        self.assertEqual(item["status"], "AGENT_REVIEW")
        self.assertTrue(needs_improvement(item))
        self.assertTrue(item["project"])
        self.assertTrue(any("指代" in issue for issue in item["ambiguityChecks"]))

    def test_fuzzy_recall_keeps_semantically_partial_official_candidate(self) -> None:
        cards = [
            design_card(
                "DiscardStrike",
                "每当你丢弃一张牌时，对随机一个敌人造成3点伤害。",
            )
        ]
        official = [
            OfficialClause(
                "ExpandedDiscardStrike",
                "扩展弃牌攻击",
                "每当你丢弃一张牌时，对随机敌人造成伤害并抽1张牌。",
                "Self",
                "Power",
                "OfficialReference/ExpandedDiscardStrike.cs",
            )
        ]

        report = audit(cards, official, {"DiscardStrike"})

        item = report["results"][0]
        self.assertEqual(item["status"], "OFFICIAL_CANDIDATE")
        self.assertEqual(item["official"][0]["className"], "ExpandedDiscardStrike")

    def test_fuzzy_recall_does_not_promote_unrelated_wording(self) -> None:
        cards = [design_card("BlockCard", "获得8点格挡。")]
        official = [
            OfficialClause(
                "Bloodletting",
                "放血",
                "失去3点生命。",
                "Self",
                "Skill",
                "OfficialReference/Bloodletting.cs",
            )
        ]

        report = audit(cards, official, {"BlockCard"})

        self.assertTrue(all(item["status"] == "AGENT_REVIEW" for item in report["results"]))

    def test_changed_keys_only_include_added_or_description_related_changes(self) -> None:
        previous = [design_card("OldCard", "造成6点伤害。")]
        current = [
            design_card("OldCard", "造成6点伤害。", note="检查官方措辞"),
            design_card("NewCard", "造成8点伤害。"),
        ]

        self.assertEqual(changed_keys(previous, current), {"OldCard", "NewCard"})

    def test_style_checks_native_keyword_and_half_width_punctuation(self) -> None:
        self.assertIn("原生关键词不应作为独立描述句重复显示", style_issues("消耗。"))
        self.assertTrue(any("半角标点" in issue for issue in style_issues("造成6点伤害(两次)")))


    def test_upgrade_consistency_allows_non_upgradable_blank(self) -> None:
        card = design_card("StatusCard", "受到2点伤害。")
        card["升级后费用"] = None
        card["升级后描述"] = None

        self.assertEqual(upgrade_consistency_issues(card), [])

    def test_upgrade_consistency_reports_blank_when_upgrade_cost_exists(self) -> None:
        card = design_card("TestCard", "造成8点伤害。")
        card["升级后描述"] = None

        self.assertTrue(any("升级后费用存在" in issue for issue in upgrade_consistency_issues(card)))
    def test_upgrade_consistency_ignores_numbers_and_keywords(self) -> None:
        card = design_card("TestCard", "造成8点伤害。")
        card["升级后描述"] = "造成10点伤害。\n保留。"

        self.assertEqual(upgrade_consistency_issues(card), [])

    def test_upgrade_consistency_reports_missing_effect_clause(self) -> None:
        card = design_card("TestCard", "造成8点伤害。\n抽2张牌。")
        card["升级后描述"] = "造成10点伤害。"

        issues = upgrade_consistency_issues(card)

        self.assertTrue(any("基础描述有2项" in issue for issue in issues))

if __name__ == "__main__":
    unittest.main()




