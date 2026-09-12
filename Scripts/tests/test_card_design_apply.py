from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from card_design_apply import (  # noqa: E402
    CardDesignApplyError,
    atomic_write_group,
    plan_card_apply,
)


def design_card(
    *,
    description: str = "造成6点伤害2次。\n你受到1点伤害2次。",
    upgraded_description: str = "造成8点伤害2次。\n你受到1点伤害2次。",
    cost: int = 1,
    upgraded_cost: int = 1,
    card_type: str = "攻击",
    rarity: str = "普通",
    target: str | None = None,
    name: str | None = None,
) -> dict[str, object]:
    return {
        "key": "Test7",
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


SOURCE = """using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.ValueProps;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test7 : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new DamageVar(6m, ValueProp.Move),
        new RepeatVar(2),
        new DamageVar("SelfDamage", 1m,
            ValueProp.Unblockable | ValueProp.Unpowered | ValueProp.Move)
    ];

    public Test7() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy) { }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(2m);
    }
}
"""


MAPPING = {
    "effects": [
        {
            "source": {"baseNumberIndex": 0, "upgradeNumberIndex": 0},
            "target": {
                "kind": "dynamicVar",
                "type": "DamageVar",
                "ordinal": 0,
                "expectedName": "Damage",
                "expectedValueProps": "ValueProp.Move",
            },
        },
        {
            "source": {"baseNumberIndex": 2, "upgradeNumberIndex": 2},
            "target": {
                "kind": "dynamicVar",
                "type": "DamageVar",
                "ordinal": 1,
                "expectedName": "SelfDamage",
                "expectedValueProps": (
                    "ValueProp.Unblockable | ValueProp.Unpowered | ValueProp.Move"
                ),
            },
        },
    ]
}


class CardDesignApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.card_path = self.workspace / "Mod" / "Cards" / "Test7.cs"
        self.card_path.parent.mkdir(parents=True)
        self.card_path.write_text(SOURCE, encoding="utf-8")
        self.localization_path = (
            self.workspace
            / "Mod"
            / "RDMod"
            / "localization"
            / "zhs"
            / "cards.json"
        )
        self.localization_path.parent.mkdir(parents=True)
        self.localization = {
            "RD_MOD_CARD_TEST7.title": "Test7",
            "RD_MOD_CARD_TEST7.description": (
                "造成{Damage:diff()}点伤害{Repeat:diff()}次。\n"
                "你受到{SelfDamage:diff()}点伤害{Repeat:diff()}次。"
            ),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def plan(self, previous: dict[str, object], current: dict[str, object]):
        return plan_card_apply(
            self.workspace,
            previous,
            current,
            MAPPING,
            self.localization,
            "RD_MOD_CARD_TEST7",
        )

    def test_updates_two_damage_vars_by_type_ordinal(self) -> None:
        current = design_card(
            description="造成7点伤害2次。\n你受到2点伤害2次。",
            upgraded_description="造成10点伤害2次。\n你受到2点伤害2次。",
        )
        result = self.plan(design_card(), current)
        self.assertIn("new DamageVar(7m, ValueProp.Move)", result.card_text)
        self.assertIn('new DamageVar("SelfDamage", 2m,', result.card_text)
        self.assertIn("DynamicVars.Damage.UpgradeValueBy(3m);", result.card_text)
        self.assertNotIn("SelfDamage\"].UpgradeValueBy", result.card_text)
        self.assertEqual(
            json.loads(result.localization_text),
            self.localization,
        )

    def test_reordered_same_type_variables_are_rejected(self) -> None:
        reordered = SOURCE.replace(
            "new DamageVar(6m, ValueProp.Move),\n        new RepeatVar(2),\n"
            '        new DamageVar("SelfDamage", 1m,\n'
            "            ValueProp.Unblockable | ValueProp.Unpowered | ValueProp.Move)",
            'new DamageVar("SelfDamage", 1m, ValueProp.Move),\n'
            "        new RepeatVar(2),\n"
            "        new DamageVar(6m, ValueProp.Move)",
        )
        self.card_path.write_text(reordered, encoding="utf-8")
        with self.assertRaisesRegex(CardDesignApplyError, "name is 'SelfDamage'"):
            self.plan(
                design_card(),
                design_card(
                    description="造成7点伤害2次。\n你受到1点伤害2次。"
                ),
            )

    def test_updates_cost_enum_target_and_title(self) -> None:
        current = design_card(
            cost=2,
            upgraded_cost=1,
            card_type="技能",
            rarity="罕见",
            target="自身",
            name="双重伤害",
        )
        result = self.plan(design_card(), current)
        self.assertIn(
            "base(2, CardType.Skill, CardRarity.Uncommon, TargetType.Self)",
            result.card_text,
        )
        self.assertIn("EnergyCost.UpgradeBy(-1);", result.card_text)
        self.assertEqual(
            json.loads(result.localization_text)["RD_MOD_CARD_TEST7.title"],
            "双重伤害",
        )

    def test_constructor_mapping_preserves_special_empty_design_fields(self) -> None:
        self.card_path.write_text(
            SOURCE.replace("CardRarity.Common", "CardRarity.Token").replace(
                "TargetType.AnyEnemy", "TargetType.AllEnemies"
            ),
            encoding="utf-8",
        )
        previous = design_card(rarity="", target=None)
        current = design_card(rarity="", target=None, cost=2, upgraded_cost=2)
        mapping = dict(MAPPING)
        mapping["constructor"] = {"rarity": "Token", "target": "AllEnemies"}
        result = plan_card_apply(
            self.workspace,
            previous,
            current,
            mapping,
            self.localization,
            "RD_MOD_CARD_TEST7",
        )
        self.assertIn(
            "base(2, CardType.Attack, CardRarity.Token, TargetType.AllEnemies)",
            result.card_text,
        )

    def test_derived_rarity_updates_constructor_to_token(self) -> None:
        result = self.plan(design_card(), design_card(rarity="衍生"))

        self.assertIn("CardRarity.Token", result.card_text)
    def test_mechanism_text_change_is_rejected_without_writing(self) -> None:
        before = self.card_path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(CardDesignApplyError, "structural changes"):
            self.plan(
                design_card(),
                design_card(description="对所有敌人造成7点伤害。"),
            )
        self.assertEqual(self.card_path.read_text(encoding="utf-8"), before)

    def test_old_code_value_drift_is_rejected(self) -> None:
        self.card_path.write_text(SOURCE.replace("DamageVar(6m", "DamageVar(9m"), encoding="utf-8")
        with self.assertRaisesRegex(CardDesignApplyError, "code value is 9"):
            self.plan(
                design_card(),
                design_card(
                    description="造成7点伤害2次。\n你受到1点伤害2次。"
                ),
            )

    def test_equal_same_type_values_still_use_ordinal(self) -> None:
        self.card_path.write_text(
            SOURCE.replace('new DamageVar("SelfDamage", 1m,', 'new DamageVar("SelfDamage", 6m,'),
            encoding="utf-8",
        )
        previous = design_card(
            description="造成6点伤害2次。\n你受到6点伤害2次。",
            upgraded_description="造成8点伤害2次。\n你受到6点伤害2次。",
        )
        current = design_card(
            description="造成6点伤害2次。\n你受到7点伤害2次。",
            upgraded_description="造成8点伤害2次。\n你受到7点伤害2次。",
        )
        result = self.plan(previous, current)
        self.assertIn("new DamageVar(6m, ValueProp.Move)", result.card_text)
        self.assertIn('new DamageVar("SelfDamage", 7m,', result.card_text)

    def test_deleted_same_type_variable_is_rejected(self) -> None:
        source = SOURCE.replace(
            ',\n        new DamageVar("SelfDamage", 1m,\n'
            "            ValueProp.Unblockable | ValueProp.Unpowered | ValueProp.Move)",
            "",
        )
        self.card_path.write_text(source, encoding="utf-8")
        with self.assertRaisesRegex(CardDesignApplyError, r"DamageVar\[1\] not found"):
            self.plan(
                design_card(),
                design_card(
                    description="造成6点伤害2次。\n你受到2点伤害2次。",
                    upgraded_description="造成8点伤害2次。\n你受到2点伤害2次。",
                ),
            )

    def test_mapped_constant_updates_fixed_localization_number(self) -> None:
        self.card_path.write_text(
            SOURCE.replace(
                "{\n    protected override",
                "{\n    private const int EnergyThreshold = 10;\n\n    protected override",
            ),
            encoding="utf-8",
        )
        mapping = {
            "effects": [
                {
                    "source": {"baseNumberIndex": 0, "upgradeNumberIndex": 0},
                    "target": {
                        "kind": "constant",
                        "name": "EnergyThreshold",
                    },
                    "localizationNumberIndex": 0,
                }
            ]
        }
        previous = design_card(
            description="耗能阈值为10。",
            upgraded_description="耗能阈值为10。",
        )
        current = design_card(
            description="耗能阈值为12。",
            upgraded_description="耗能阈值为12。",
        )
        localization = dict(self.localization)
        localization["RD_MOD_CARD_TEST7.description"] = "耗能阈值为10。"
        result = plan_card_apply(
            self.workspace,
            previous,
            current,
            mapping,
            localization,
            "RD_MOD_CARD_TEST7",
        )
        self.assertIn("EnergyThreshold = 12;", result.card_text)
        self.assertEqual(
            json.loads(result.localization_text)["RD_MOD_CARD_TEST7.description"],
            "耗能阈值为12。",
        )

    def test_atomic_write_group_restores_first_file_if_second_replace_fails(self) -> None:
        first = self.workspace / "first.txt"
        second = self.workspace / "second.txt"
        first.write_text("old-first", encoding="utf-8")
        second.write_text("old-second", encoding="utf-8")
        real_replace = os.replace
        calls = 0

        def fail_second_replace(source: str | Path, destination: str | Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated replace failure")
            real_replace(source, destination)

        with mock.patch("card_design_apply.os.replace", side_effect=fail_second_replace):
            with self.assertRaisesRegex(OSError, "simulated"):
                atomic_write_group({first: b"new-first", second: b"new-second"})
        self.assertEqual(first.read_text(encoding="utf-8"), "old-first")
        self.assertEqual(second.read_text(encoding="utf-8"), "old-second")


if __name__ == "__main__":
    unittest.main()

