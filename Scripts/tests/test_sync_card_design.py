from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_card_design import (  # noqa: E402
    affected_files,
    design_diff,
    filter_diff,
    merge_selected_cards,
    target_from_description,
    target_from_note,
)


def card(key: str, name: str, cost: int = 1) -> dict[str, object]:
    return {
        "key": key, "名称": name, "稀有度": "普通", "类型": "攻击", "费用": cost,
        "描述": "造成伤害。", "升级后费用": cost, "升级后描述": "造成更多伤害。",
        "目标": "任意敌人", "备注": None,
    }


class SyncCardDesignTests(unittest.TestCase):
    def test_note_change_affects_code_and_localization(self) -> None:
        self.assertEqual(
            affected_files("Test1", ["备注"]),
            ["Mod/Cards/Test1.cs", "Mod/RDMod/localization/zhs/cards.json"],
        )

    def test_special_target_is_inferred_from_unambiguous_description(self) -> None:
        self.assertEqual(target_from_description("对所有敌人造成7点伤害。"), "AllEnemies")
        self.assertEqual(target_from_description("随机对敌人造成9点伤害3次。"), "RandomEnemy")
        self.assertEqual(target_from_description("对随机一个敌人造成2点伤害。"), "RandomEnemy")
        self.assertIsNone(target_from_description("造成7点伤害。"))

    def test_target_is_extracted_only_from_an_explicit_note_line(self) -> None:
        note = "战斗中补充描述：\n（攻击X次）\n目标：随机敌人"
        self.assertEqual(target_from_note(note), "随机敌人")
        self.assertEqual(target_from_note("选择目标后显示提示。"), None)
        self.assertEqual(target_from_note("目标: 所有敌人"), "所有敌人")

    def test_empty_or_duplicate_target_declarations_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Empty target declaration"):
            target_from_note("目标：")
        with self.assertRaisesRegex(ValueError, "Multiple target declarations"):
            target_from_note("目标：自身\n目标：所有敌人")
        with self.assertRaisesRegex(ValueError, "Unsupported target declaration"):
            target_from_note("目标：附近敌人")

    def test_omitted_target_equals_explicit_type_default(self) -> None:
        previous = [card("Test1", "一")]
        current = [card("Test1", "一")]
        current[0]["目标"] = None
        self.assertEqual(design_diff(previous, current)["summary"]["changed"], 0)

    def test_special_target_change_is_reported(self) -> None:
        previous = [card("Test1", "一")]
        current = [card("Test1", "一")]
        current[0]["目标"] = "随机敌人"
        changes = design_diff(previous, current)["changed"][0]["changes"]
        self.assertEqual(changes, [{"field": "目标", "before": None, "after": "随机敌人"}])

    def test_filter_diff_keeps_only_requested_key(self) -> None:
        diff = design_diff([card("Test1", "一"), card("Test2", "二")], [card("Test1", "一", 2), card("Test2", "二", 2)])
        filtered = filter_diff(diff, {"Test2"})
        self.assertEqual([item["key"] for item in filtered["changed"]], ["Test2"])
        self.assertEqual(filtered["summary"]["changed"], 1)

    def test_partial_accept_updates_only_requested_key(self) -> None:
        previous = [card("Test1", "一"), card("Test2", "二")]
        current = [card("Test1", "一", 2), card("Test2", "二", 2)]
        merged = merge_selected_cards(previous, current, {"Test2"})
        self.assertEqual([item["费用"] for item in merged], [1, 2])

    def test_partial_accept_can_remove_selected_key(self) -> None:
        merged = merge_selected_cards([card("Test1", "一")], [], {"Test1"})
        self.assertEqual(merged, [])


if __name__ == "__main__":
    unittest.main()
