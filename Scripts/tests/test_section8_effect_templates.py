from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from card_effect_templates import (  # noqa: E402
    EFFECT_TEMPLATES,
    TemplateRegistry,
    TemplateRegistryError,
)
from scaffold_card import (  # noqa: E402
    ScaffoldError,
    build_spec,
    parse_effect_list,
    write_scaffold,
)


def design(
    key: str,
    description: str,
    upgraded_description: str,
    *,
    card_type: str = "攻击",
    target: str | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "名称": None,
        "稀有度": "普通",
        "类型": card_type,
        "费用": 1,
        "描述": description,
        "升级后费用": 1,
        "升级后描述": upgraded_description,
        "目标": target,
        "备注": None,
    }


class Section8EffectTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        localization = (
            self.workspace / "Mod" / "RDMod" / "localization" / "zhs" / "cards.json"
        )
        localization.parent.mkdir(parents=True)
        localization.write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_matches_verified_atomic_templates(self) -> None:
        effects = parse_effect_list(
            "消耗。保留。固有。造成2点伤害4次。"
            "你受到1点伤害2次。"
            "如果你拥有蓄力，抽1张牌。"
            "如果你拥有飞行，先给予2层易伤。"
            "如果你拥有蓄力，给予2层虚弱。"
            "将一张失控加入你的手牌。",
            "描述",
        )
        self.assertEqual(
            [effect.template_id for effect in effects],
            [
                "exhaust",
                "retain",
                "innate",
                "multi_hit_damage",
                "repeated_card_self_damage",
                "draw_with_preparation",
                "vulnerable_before_damage_with_flight",
                "weak_with_preparation",
                "generate_out_of_control_to_hand",
            ],
        )

    def test_generates_section8_control_flow(self) -> None:
        cases = (
            design(
                "MultiOutOfControl",
                "造成2点伤害4次。将一张失控加入你的手牌。",
                "造成3点伤害4次。将一张失控加入你的手牌。",
            ),
            design(
                "SelfDamage",
                "造成6点伤害2次。你受到1点伤害2次。",
                "造成8点伤害2次。你受到1点伤害2次。",
            ),
            design(
                "FlightVulnerable",
                "如果你拥有飞行，先给予2层易伤。造成7点伤害。",
                "如果你拥有飞行，先给予3层易伤。造成8点伤害。",
            ),
            design(
                "PreparationWeak",
                "造成7点伤害。如果你拥有蓄力，给予2层虚弱。",
                "造成8点伤害。如果你拥有蓄力，给予3层虚弱。",
            ),
            design(
                "PreparationDraw",
                "造成5点伤害。如果你拥有蓄力，抽1张牌。",
                "造成8点伤害。如果你拥有蓄力，抽1张牌。",
            ),
        )
        snippets = {
            "MultiOutOfControl": ["WithHitCount", "CreateCard<OutOfControl>"],
            "SelfDamage": ["SelfDamageRepeat", "CreatureCmd.Damage"],
            "FlightVulnerable": ["GetPower<FlightPower>", "VulnerablePower"],
            "PreparationWeak": ["GetPower<PreparationPower>", "WeakPower"],
            "PreparationDraw": ["GetPower<PreparationPower>", "CardPileCmd.Draw"],
        }
        for card in cases:
            spec = build_spec(card)
            self.assertTrue(spec.is_complete, card["key"])
            write_scaffold(self.workspace, spec, dry_run=False)
            source = (
                self.workspace / "Mod" / "Cards" / f"{card['key']}.cs"
            ).read_text(encoding="utf-8")
            for snippet in snippets[str(card["key"])]:
                self.assertIn(snippet, source)

    def test_generates_keywords_and_all_enemy_target(self) -> None:
        spec = build_spec(
            design(
                "CleaveExhaust",
                "对所有敌人造成8点伤害。消耗。",
                "对所有敌人造成11点伤害。消耗。",
                target="所有敌人",
            )
        )
        self.assertEqual(spec.target, "AllEnemies")
        write_scaffold(self.workspace, spec, dry_run=False)
        source = (
            self.workspace / "Mod" / "Cards" / "CleaveExhaust.cs"
        ).read_text(encoding="utf-8")
        self.assertIn("CardKeyword.Exhaust", source)
        self.assertIn("TargetingAllOpponents", source)

    def test_rejects_near_matches_and_changed_repeat_count(self) -> None:
        for text in (
            "造成2点伤害很多次。",
            "你失去1点生命2次。",
            "如果你没有蓄力，抽1张牌。",
            "如果你拥有飞行，给予2层易伤。",
            "将两张失控加入你的手牌。",
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ScaffoldError, "unsupported effects"):
                    parse_effect_list(text, "描述")

        spec = build_spec(
            design(
                "ChangedRepeat",
                "造成2点伤害4次。",
                "造成2点伤害5次。",
            ),
            allow_partial=True,
        )
        self.assertFalse(spec.effect_upgrades_supported)
        self.assertFalse(spec.is_complete)

    def test_registry_reports_multi_hit_ambiguity(self) -> None:
        original_type = type(EFFECT_TEMPLATES.get("multi_hit_damage"))

        class DuplicateMultiHitTemplate(original_type):
            template_id = "duplicate_multi_hit"

        registry = TemplateRegistry(
            (EFFECT_TEMPLATES.get("multi_hit_damage"), DuplicateMultiHitTemplate())
        )
        with self.assertRaisesRegex(TemplateRegistryError, "Ambiguous"):
            registry.match("造成2点伤害4次")


if __name__ == "__main__":
    unittest.main()
