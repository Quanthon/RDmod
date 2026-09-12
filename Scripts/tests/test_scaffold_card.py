from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scaffold_card import (  # noqa: E402
    ScaffoldError,
    audit_cards,
    build_spec,
    parse_effect_list,
    write_scaffold,
)
from card_effect_templates import (  # noqa: E402
    DamageTemplate,
    DoublePreparationTemplate,
    TemplateRegistry,
    TemplateRegistryError,
)


def card_design(
    *,
    key: str = "TestCard",
    name: str | None = None,
    card_type: str = "攻击",
    rarity: str = "普通",
    cost: int = 1,
    description: str = "造成7点伤害。\n获得4点格挡。",
    upgraded_cost: int = 1,
    upgraded_description: str = "造成10点伤害。\n获得6点格挡。",
    target: str | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "名称": name,
        "稀有度": rarity,
        "类型": card_type,
        "费用": cost,
        "描述": description,
        "升级后费用": upgraded_cost,
        "升级后描述": upgraded_description,
        "目标": target,
        "备注": None,
    }


class ScaffoldCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        localization = (
            self.workspace
            / "Mod"
            / "RDMod"
            / "localization"
            / "zhs"
            / "cards.json"
        )
        localization.parent.mkdir(parents=True)
        localization.write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_generates_standard_card_localization_and_art(self) -> None:
        spec = build_spec(card_design())

        outputs = write_scaffold(self.workspace, spec, dry_run=False)

        card_path = self.workspace / "Mod" / "Cards" / "TestCard.cs"
        art_path = (
            self.workspace
            / "Mod"
            / "RDMod"
            / "images"
            / "cards"
            / "TestCard.png"
        )
        card_text = card_path.read_text(encoding="utf-8")
        localization = json.loads(
            (
                self.workspace
                / "Mod"
                / "RDMod"
                / "localization"
                / "zhs"
                / "cards.json"
            ).read_text(encoding="utf-8")
        )

        mapping = json.loads(
            (self.workspace / "design" / "card-design-mappings.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(outputs["mapping_status"], "written")
        self.assertEqual(outputs["mapping_effects"], 2)
        self.assertIn("TestCard", mapping["cards"])
        self.assertEqual(outputs["art_status"], "generated")
        self.assertTrue(art_path.is_file())
        self.assertTrue(art_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("CardRarity.Common, TargetType.AnyEnemy", card_text)
        self.assertIn("new DamageVar(7m, ValueProp.Move)", card_text)
        self.assertIn("new BlockVar(4m, ValueProp.Move)", card_text)
        self.assertIn("DynamicVars.Damage.UpgradeValueBy(3m);", card_text)
        self.assertIn("DynamicVars.Block.UpgradeValueBy(2m);", card_text)
        self.assertEqual(localization["RD_MOD_CARD_TEST_CARD.title"], "TestCard")
        self.assertEqual(
            localization["RD_MOD_CARD_TEST_CARD.description"],
            "造成{Damage:diff()}点伤害。\n"
            "获得{Block:diff()}点[gold]格挡[/gold]。",
        )

    def test_derived_rarity_maps_to_token(self) -> None:
        spec = build_spec(card_design(rarity="衍生"))

        self.assertEqual(spec.rarity, "Token")

    def test_ancient_rarity_maps_to_ancient(self) -> None:
        spec = build_spec(card_design(rarity="先古"))

        self.assertEqual(spec.rarity, "Ancient")
    def test_rejects_unknown_effect_before_writing(self) -> None:
        design = card_design(
            key="Test20",
            description="造成13点伤害。\n超速打出后，获得3层飞行。",
            upgraded_description="造成15点伤害。\n超速打出后，获得4层飞行。",
        )

        with self.assertRaisesRegex(ScaffoldError, "unsupported effects"):
            build_spec(design)

        self.assertFalse(
            (self.workspace / "Mod" / "Cards" / "Test20.cs").exists()
        )

    def test_reuses_existing_art_without_overwriting(self) -> None:
        spec = build_spec(
            card_design(
                key="Test36",
                card_type="技能",
                rarity="罕见",
                description="获得2层飞行。\n获得2层蓄力。",
                upgraded_description="获得2层飞行。\n获得3层蓄力。",
            )
        )
        art_path = (
            self.workspace
            / "Mod"
            / "RDMod"
            / "images"
            / "cards"
            / "Test36.png"
        )
        art_path.parent.mkdir(parents=True)
        art_path.write_bytes(b"formal-art")

        outputs = write_scaffold(self.workspace, spec, dry_run=False)

        self.assertEqual(outputs["art_status"], "reused")
        self.assertEqual(art_path.read_bytes(), b"formal-art")
        card_text = (
            self.workspace / "Mod" / "Cards" / "Test36.cs"
        ).read_text(encoding="utf-8")
        self.assertIn("new PowerVar<FlightPower>(2m)", card_text)
        self.assertIn("new PowerVar<PreparationPower>(2m)", card_text)
        self.assertIn("PowerCmd.Apply<FlightPower>", card_text)
        self.assertIn(
            'DynamicVars["PreparationPower"].UpgradeValueBy(1m);',
            card_text,
        )

    def test_generates_draw_and_energy_templates(self) -> None:
        spec = build_spec(
            card_design(
                key="TestResources",
                card_type="技能",
                description="获得[1能量]。\n抽2张牌。",
                upgraded_description="获得[2能量]。\n抽3张牌。",
            )
        )

        write_scaffold(self.workspace, spec, dry_run=False)

        card_text = (
            self.workspace / "Mod" / "Cards" / "TestResources.cs"
        ).read_text(encoding="utf-8")
        self.assertIn("new EnergyVar(1)", card_text)
        self.assertIn("new CardsVar(2)", card_text)
        self.assertIn("PlayerCmd.GainEnergy", card_text)
        self.assertIn("CardPileCmd.Draw", card_text)
        self.assertIn("DynamicVars.Energy.UpgradeValueBy(1m);", card_text)
        self.assertIn("DynamicVars.Cards.UpgradeValueBy(1m);", card_text)

    def test_dry_run_writes_nothing(self) -> None:
        spec = build_spec(card_design(key="TestDryRun"))

        outputs = write_scaffold(self.workspace, spec, dry_run=True)

        self.assertFalse(
            (self.workspace / "Mod" / "Cards" / "TestDryRun.cs").exists()
        )
        localization = json.loads(
            (
                self.workspace
                / "Mod"
                / "RDMod"
                / "localization"
                / "zhs"
                / "cards.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(localization, {})
        self.assertEqual(outputs["mapping_status"], "preview")
        self.assertFalse(
            (self.workspace / "design" / "card-design-mappings.json").exists()
        )

    def test_existing_mapping_rejects_scaffold_before_writing(self) -> None:
        mapping_path = self.workspace / "design" / "card-design-mappings.json"
        mapping_path.parent.mkdir(parents=True)
        mapping_path.write_text(
            json.dumps({"schemaVersion": 1, "cards": {"MappedCard": {}}}),
            encoding="utf-8",
        )
        spec = build_spec(card_design(key="MappedCard"))

        with self.assertRaisesRegex(ScaffoldError, "mapping already exists"):
            write_scaffold(self.workspace, spec, dry_run=False)

        self.assertFalse(
            (self.workspace / "Mod" / "Cards" / "MappedCard.cs").exists()
        )
        localization = json.loads(
            (
                self.workspace
                / "Mod"
                / "RDMod"
                / "localization"
                / "zhs"
                / "cards.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(localization, {})

    def test_mapping_write_failure_rolls_back_scaffold_outputs(self) -> None:
        spec = build_spec(card_design(key="RollbackCard"))
        real_replace = os.replace

        def fail_mapping_replace(source: object, destination: object) -> None:
            if Path(destination).name == "card-design-mappings.json":
                raise OSError("simulated mapping write failure")
            real_replace(source, destination)

        with patch("card_design_apply.os.replace", side_effect=fail_mapping_replace):
            with self.assertRaisesRegex(OSError, "simulated mapping write failure"):
                write_scaffold(self.workspace, spec, dry_run=False)

        self.assertFalse(
            (self.workspace / "Mod" / "Cards" / "RollbackCard.cs").exists()
        )
        self.assertFalse(
            (
                self.workspace
                / "Mod"
                / "RDMod"
                / "images"
                / "cards"
                / "RollbackCard.png"
            ).exists()
        )
        self.assertFalse(
            (self.workspace / "design" / "card-design-mappings.json").exists()
        )

    def test_effects_are_independent_registered_templates(self) -> None:
        effects = parse_effect_list("获得2层飞行。获得2层蓄力。", "描述")

        self.assertEqual(
            [effect.template_id for effect in effects],
            ["gain_flight", "gain_preparation"],
        )

    def test_recognizes_native_sly_and_rejects_near_matches(self) -> None:
        effects = parse_effect_list("奇巧。造成4点伤害。", "描述")

        self.assertEqual(
            [effect.template_id for effect in effects],
            ["native_sly", "direct_damage"],
        )
        with self.assertRaisesRegex(ScaffoldError, "unsupported effects"):
            parse_effect_list("获得奇巧。", "描述")

    def test_generates_native_sly_in_partial_card(self) -> None:
        spec = build_spec(
            card_design(
                key="SlyDraft",
                description="奇巧。\n消耗。\n造成4点伤害。",
                upgraded_description="奇巧。\n消耗。\n造成6点伤害。",
            ),
            allow_partial=True,
        )

        write_scaffold(self.workspace, spec, dry_run=False)
        card_text = (
            self.workspace / "Mod" / "Cards" / "SlyDraft.cs"
        ).read_text(encoding="utf-8")
        self.assertIn("CanonicalKeywords", card_text)
        self.assertIn("CardKeyword.Sly", card_text)
        self.assertIn("DamageCmd.Attack", card_text)

    def test_recognizes_section_32_event_templates(self) -> None:
        effects = parse_effect_list(
            "每回合第一次获得飞行时，获得[1能量]。"
            "在你的回合开始时，获得1层蓄力。"
            "当你拥有飞行时，获得2点力量。"
            "你的蓄力层数翻倍。"
            "在你的下一回合结束前，飞行层数不会减少。",
            "描述",
        )

        self.assertEqual(
            [effect.template_id for effect in effects],
            [
                "first_flight_energy_per_turn",
                "gain_preparation_at_turn_start",
                "strength_while_flying",
                "double_preparation",
                "preserve_flight_until_next_turn_end",
            ],
        )

    def test_generates_section_32_known_effects_in_partial_cards(self) -> None:
        designs = [
            card_design(
                key="FirstFlight",
                card_type="能力",
                description="每回合第一次获得飞行时，获得[1能量]。",
                upgraded_cost=0,
                upgraded_description="每回合第一次获得飞行时，获得[1能量]。",
            ),
            card_design(
                key="TurnPrep",
                card_type="能力",
                description="在你的回合开始时，获得1层蓄力。",
                upgraded_cost=0,
                upgraded_description="在你的回合开始时，获得1层蓄力。",
            ),
            card_design(
                key="FlightStrength",
                card_type="能力",
                description="当你拥有飞行时，获得2点力量。",
                upgraded_description="当你拥有飞行时，获得3点力量。",
            ),
            card_design(
                key="DoublePrep",
                card_type="技能",
                description="你的蓄力层数翻倍。\n消耗。",
                upgraded_cost=0,
                upgraded_description="你的蓄力层数翻倍。\n消耗。",
            ),
            card_design(
                key="KeepFlight",
                card_type="技能",
                description="获得1层飞行。\n在你的下一回合结束前，飞行层数不会减少。\n消耗。",
                upgraded_description="获得2层飞行。\n在你的下一回合结束前，飞行层数不会减少。\n消耗。",
            ),
        ]

        snippets = {
            "FirstFlight": "PowerCmd.Apply<FirstFlightEnergyPower>",
            "TurnPrep": "PowerCmd.Apply<TurnPreparationPower>",
            "FlightStrength": "PowerCmd.Apply<FlightStrengthPower>",
            "DoublePrep": "PowerCmd.ModifyAmount(",
            "KeepFlight": "PowerCmd.Apply<FlightPreservationPower>",
        }
        for design in designs:
            spec = build_spec(design, allow_partial=True)
            write_scaffold(self.workspace, spec, dry_run=False)
            card_text = (
                self.workspace / "Mod" / "Cards" / f"{design['key']}.cs"
            ).read_text(encoding="utf-8")
            self.assertIn(snippets[str(design["key"])], card_text)

    def test_section_32_templates_reject_near_matches(self) -> None:
        with self.assertRaisesRegex(ScaffoldError, "unsupported effects"):
            parse_effect_list(
                "每回合第二次获得飞行时，获得[1能量]。"
                "你的飞行层数翻倍。",
                "描述",
            )

    def test_registry_rejects_ambiguous_section_32_template(self) -> None:
        class DuplicateDoublePreparationTemplate(DoublePreparationTemplate):
            template_id = "duplicate_double_preparation"

        registry = TemplateRegistry(
            (DoublePreparationTemplate(), DuplicateDoublePreparationTemplate())
        )

        with self.assertRaisesRegex(TemplateRegistryError, "Ambiguous"):
            registry.match("你的蓄力层数翻倍")

    def test_registry_rejects_ambiguous_patterns(self) -> None:
        class DuplicateDamageTemplate(DamageTemplate):
            template_id = "duplicate_damage"

        registry = TemplateRegistry(
            (DamageTemplate(), DuplicateDamageTemplate())
        )

        with self.assertRaisesRegex(TemplateRegistryError, "Ambiguous"):
            registry.match("造成7点伤害")

    def test_audit_reports_coverage_without_writing(self) -> None:
        report = audit_cards(
            [
                card_design(key="Supported"),
                card_design(
                    key="Manual",
                    description="未注册效果。",
                    upgraded_description="未注册效果。",
                ),
            ]
        )

        self.assertEqual(report["card_count"], 2)
        self.assertEqual(report["fully_supported_card_count"], 1)
        self.assertEqual(report["partial_card_count"], 1)
        self.assertEqual(report["rejected_card_count"], 0)
        self.assertEqual(report["base_clause_count"], 3)
        self.assertEqual(report["recognized_base_clause_count"], 2)
        self.assertEqual(report["template_usage"]["direct_damage"], 1)
        self.assertEqual(report["template_usage"]["gain_block"], 1)
        self.assertEqual(report["unsupported_segments"][0], {
            "segment": "未注册效果",
            "count": 1,
        })
        self.assertFalse((self.workspace / "Mod" / "Cards").exists())

    def test_audit_excludes_registered_implementations(self) -> None:
        report = audit_cards(
            [
                card_design(key="Implemented"),
                card_design(
                    key="Missing",
                    description="未注册效果。",
                    upgraded_description="未注册效果。",
                ),
            ],
            implemented_keys={"Implemented"},
        )

        self.assertEqual(report["workbook_card_count"], 2)
        self.assertEqual(report["implemented_card_count"], 1)
        self.assertEqual(report["unimplemented_card_count"], 1)
        self.assertEqual(report["card_count"], 1)
        self.assertEqual(report["fully_supported_card_count"], 0)
        self.assertEqual(report["partial_card_count"], 1)
        self.assertEqual([card["key"] for card in report["cards"]], ["Missing"])

    def test_partial_scaffold_keeps_metadata_and_known_effects(self) -> None:
        spec = build_spec(
            card_design(
                key="PartialCard",
                cost=2,
                description="造成7点伤害。\n未知效果。",
                upgraded_cost=1,
                upgraded_description="造成10点伤害。\n未知效果。",
                target="任意敌人",
            ),
            allow_partial=True,
        )

        self.assertFalse(spec.is_complete)
        self.assertEqual(spec.cost, 2)
        self.assertEqual(spec.upgraded_cost, 1)
        self.assertEqual(spec.target, "AnyEnemy")
        self.assertEqual(
            [effect.template_id for effect in spec.effects],
            ["direct_damage"],
        )
        self.assertEqual(spec.unsupported_effects, ("未知效果",))

        outputs = write_scaffold(self.workspace, spec, dry_run=False)
        card_text = (
            self.workspace / "Mod" / "Cards" / "PartialCard.cs"
        ).read_text(encoding="utf-8")
        localization = json.loads(
            (
                self.workspace
                / "Mod"
                / "RDMod"
                / "localization"
                / "zhs"
                / "cards.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(outputs["status"], "partial")
        self.assertEqual(outputs["mapping_status"], "pending")
        self.assertFalse(
            (self.workspace / "design" / "card-design-mappings.json").exists()
        )
        self.assertNotIn("[RegisterCard", card_text)
        self.assertIn("PARTIAL SCAFFOLD", card_text)
        self.assertIn("TODO(scaffold-effect): 未知效果", card_text)
        self.assertIn(
            "base(2, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy)",
            card_text,
        )
        self.assertIn("DamageCmd.Attack", card_text)
        self.assertIn("EnergyCost.UpgradeBy(-1);", card_text)
        self.assertEqual(
            localization["RD_MOD_CARD_PARTIAL_CARD.description"],
            "造成7点伤害。\n未知效果。",
        )

    def test_explicit_special_and_uncertain_targets_are_preserved(self) -> None:
        all_enemies = build_spec(
            card_design(
                key="AllEnemiesDraft",
                description="对所有敌人造成8点伤害。",
                upgraded_description="对所有敌人造成11点伤害。",
                target="所有敌人",
            ),
            allow_partial=True,
        )
        uncertain = build_spec(
            card_design(
                key="UncertainDraft",
                card_type="技能",
                description="选择一张手牌。",
                upgraded_description="选择两张手牌。",
                target="待确认",
            ),
            allow_partial=True,
        )

        self.assertEqual(all_enemies.target, "AllEnemies")
        self.assertTrue(all_enemies.is_complete)
        self.assertEqual(uncertain.target, "Self")
        self.assertTrue(
            any("目标标记为" in reason for reason in uncertain.partial_reasons)
        )

    def test_special_target_is_inferred_without_note_override(self) -> None:
        all_enemies = build_spec(
            card_design(
                description="对所有敌人造成8点伤害。",
                upgraded_description="对所有敌人造成11点伤害。",
            ),
            allow_partial=True,
        )
        random_enemy = build_spec(
            card_design(
                description="随机对敌人造成3点伤害3次。",
                upgraded_description="随机对敌人造成5点伤害3次。",
            ),
            allow_partial=True,
        )

        self.assertEqual(all_enemies.target, "AllEnemies")
        self.assertEqual(random_enemy.target, "RandomEnemy")

    def test_invalid_target_is_rejected_before_writing(self) -> None:
        with self.assertRaisesRegex(ScaffoldError, "Unsupported 目标"):
            build_spec(
                card_design(target="附近敌人"),
                allow_partial=True,
            )


if __name__ == "__main__":
    unittest.main()

