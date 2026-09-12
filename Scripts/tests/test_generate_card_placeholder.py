from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_card_placeholder import CARD_TYPE_COLORS, normalize_card_type, render_placeholder


class GenerateCardPlaceholderTests(unittest.TestCase):
    def test_type_aliases_render_expected_background(self) -> None:
        for alias, card_type in {
            "攻击": "Attack", "Attack": "Attack",
            "技能": "Skill", "Skill": "Skill",
            "能力": "Power", "Power": "Power",
            "状态": "Status", "Status": "Status",
            "诅咒": "Curse", "Curse": "Curse",
        }.items():
            with self.subTest(alias=alias):
                image = Image.open(io.BytesIO(render_placeholder("Test", alias)))
                self.assertEqual(image.getpixel((20, 20)), CARD_TYPE_COLORS[card_type][:3])

    def test_default_and_unknown_type(self) -> None:
        image = Image.open(io.BytesIO(render_placeholder("Test")))
        self.assertEqual(image.getpixel((20, 20)), CARD_TYPE_COLORS["Status"][:3])
        with self.assertRaises(ValueError):
            normalize_card_type("未知")


if __name__ == "__main__":
    unittest.main()
