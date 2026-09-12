from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from debug_after_code import (  # noqa: E402
    RD_MOD_SUCCESS_MARKERS,
    validate_localization_json,
    validate_native_keyword_localization,
    validate_rdmod_log,
)


class DebugAfterCodeTests(unittest.TestCase):
    def test_accepts_complete_rdmod_initialization_log(self) -> None:
        ready, failure = validate_rdmod_log("\n".join(RD_MOD_SUCCESS_MARKERS))
        self.assertTrue(ready)
        self.assertIsNone(failure)

    def test_rejects_duplicate_capability_registration(self) -> None:
        text = "\n".join(RD_MOD_SUCCESS_MARKERS) + "\nDefault capability modifier is already registered: RDMod/x"
        ready, failure = validate_rdmod_log(text)
        self.assertFalse(ready)
        self.assertIn("Default capability modifier", failure or "")

    def test_waits_for_all_success_markers(self) -> None:
        ready, failure = validate_rdmod_log(RD_MOD_SUCCESS_MARKERS[0])
        self.assertFalse(ready)
        self.assertIsNone(failure)

    def test_validates_all_localization_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cards.json").write_text('{"ok": true}', encoding="utf-8")
            nested = root / "zhs"
            nested.mkdir()
            (nested / "powers.json").write_text('{"ok": true}', encoding="utf-8")

            self.assertEqual(2, validate_localization_json(root))

    def test_reports_invalid_localization_json_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cards.json").write_text('{"ok": true}\n{"extra": true}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"cards\.json:2:1"):
                validate_localization_json(root)

    def test_rejects_standalone_native_keyword_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards_dir = root / "Cards"
            cards_dir.mkdir()
            (cards_dir / "TestCard.cs").write_text(
                "[RegisterCard(typeof(TestPool))]\n"
                "public sealed class TestCard {\n"
                "public override IEnumerable<CardKeyword> CanonicalKeywords => "
                "[CardKeyword.Exhaust];\n}",
                encoding="utf-8",
            )
            cards_json = root / "cards.json"
            cards_json.write_text(
                '{"RD_MOD_CARD_TEST_CARD.description": "获得3点格挡。\\n[gold]消耗[/gold]。"}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, r"TestCard: Exhaust"):
                validate_native_keyword_localization(cards_dir, cards_json)

    def test_allows_keyword_words_inside_effect_sentences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards_dir = root / "Cards"
            cards_dir.mkdir()
            (cards_dir / "StatusCard.cs").write_text(
                "[RegisterCard(typeof(TestPool))]\n"
                "public sealed class StatusCard {\n"
                "protected override IEnumerable<IHoverTip> AdditionalHoverTips => "
                "[HoverTipFactory.FromKeyword(CardKeyword.Exhaust)];\n}",
                encoding="utf-8",
            )
            (cards_dir / "RetainCard.cs").write_text(
                "[RegisterCard(typeof(TestPool))]\n"
                "public sealed class RetainCard {\n"
                "protected override void OnUpgrade() => AddKeyword(CardKeyword.Retain);\n}",
                encoding="utf-8",
            )
            cards_json = root / "cards.json"
            cards_json.write_text(
                '{'
                '"RD_MOD_CARD_STATUS_CARD.description": "消耗手牌中的状态牌。",'
                '"RD_MOD_CARD_RETAIN_CARD.description": "在本回合保留你的攻击牌。"'
                '}',
                encoding="utf-8",
            )

            self.assertEqual(
                2,
                validate_native_keyword_localization(cards_dir, cards_json),
            )


if __name__ == "__main__":
    unittest.main()
