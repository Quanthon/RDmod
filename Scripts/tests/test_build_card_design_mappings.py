from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_card_design_mappings import (  # noqa: E402
    build_mapping_payload,
    candidate_for_card,
    write_mapping_file,
)
from card_design_apply import CardDesignApplyError, _constructor_args  # noqa: E402


DESCRIPTION = "\u63cf\u8ff0"
UPGRADED_DESCRIPTION = "\u5347\u7ea7\u540e\u63cf\u8ff0"


class BuildCardDesignMappingsTests(unittest.TestCase):
    def workspace_with_card(self, directory: str, key: str, source: str) -> Path:
        workspace = Path(directory)
        cards_dir = workspace / "Mod" / "Cards"
        cards_dir.mkdir(parents=True)
        with (cards_dir / f"{key}.cs").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            stream.write(source)
        return workspace

    def card(self, key: str, description: str, upgraded: str = "") -> dict[str, str]:
        return {
            "key": key,
            DESCRIPTION: description,
            UPGRADED_DESCRIPTION: upgraded,
        }

    def test_maps_annotated_dynamic_variable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestSingle",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestSingle : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<StrengthPower>(3m)
    ];
    public TestSingle() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
    protected override void OnUpgrade() => DynamicVars.Strength.UpgradeValueBy(1m);
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card("TestSingle", "Gain 3 Strength.", "Gain 4 Strength."),
            )
            self.assertEqual(
                candidate["effects"][0]["target"]["expectedName"], "StrengthPower"
            )
            self.assertEqual(candidate["audit"]["unmappedBaseNumberIndices"], [])

    def test_accepts_crlf_and_annotation_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = """[RegisterCard(typeof(TestPool))]
public sealed class TestCrlf : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        //   RDDesign:   base[0] , upgrade[0]
        new CardsVar(2)
    ];
    public TestCrlf() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""".replace("\n", "\r\n")
            workspace = self.workspace_with_card(directory, "TestCrlf", source)
            candidate = candidate_for_card(
                workspace, self.card("TestCrlf", "Draw 2 cards.", "Draw 2 cards.")
            )
            self.assertEqual(len(candidate["effects"]), 1)

    def test_annotation_can_omit_upgrade_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestBaseOnly",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestBaseOnly : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0]
        new CardsVar(2)
    ];
    public TestBaseOnly() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace, self.card("TestBaseOnly", "Draw 2 cards.")
            )
            self.assertNotIn(
                "upgradeNumberIndex", candidate["effects"][0]["source"]
            )

    def test_maps_named_constant_and_localization_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestConstant",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestConstant : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int Threshold = 10;
    public TestConstant() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            localization_dir = workspace / "Mod" / "RDMod" / "localization" / "zhs"
            localization_dir.mkdir(parents=True)
            (localization_dir / "cards.json").write_text(
                json.dumps(
                    {"RD_MOD_CARD_TEST_CONSTANT.description": "Threshold 10."}
                ),
                encoding="utf-8",
            )
            candidate = candidate_for_card(
                workspace,
                self.card(
                    "TestConstant", "Threshold 10.", "Threshold 10."
                ),
            )
            effect = candidate["effects"][0]
            self.assertEqual(
                effect["target"], {"kind": "constant", "name": "Threshold"}
            )
            self.assertEqual(effect["localizationNumberIndex"], 0)

    def test_equal_numbers_require_independent_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestIndependent",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestIndependent : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("FirstAmount", 1m),
        // RDDesign: base[1], upgrade[1]
        new DynamicVar("SecondAmount", 1m)
    ];
    public TestIndependent() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card(
                    "TestIndependent", "First 1, second 1.", "First 1, second 1."
                ),
            )
            names = [
                effect["target"]["expectedName"] for effect in candidate["effects"]
            ]
            self.assertEqual(names, ["FirstAmount", "SecondAmount"])

    def test_duplicate_source_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestDuplicate",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestDuplicate : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("FirstAmount", 1m),
        // RDDesign: base[0], upgrade[1]
        new DynamicVar("SecondAmount", 1m)
    ];
    public TestDuplicate() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            with self.assertRaisesRegex(CardDesignApplyError, "duplicate RDDesign base"):
                candidate_for_card(
                    workspace,
                    self.card(
                        "TestDuplicate", "First 1, second 1.", "First 1, second 1."
                    ),
                )

    def test_out_of_range_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestRange",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestRange : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[1]
        new CardsVar(2)
    ];
    public TestRange() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            with self.assertRaisesRegex(CardDesignApplyError, "out of range"):
                candidate_for_card(
                    workspace, self.card("TestRange", "Draw 2 cards.")
                )

    def test_non_adjacent_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestGap",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestGap : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0]
        // unrelated comment
        new CardsVar(2)
    ];
    public TestGap() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            with self.assertRaisesRegex(CardDesignApplyError, "immediately followed"):
                candidate_for_card(workspace, self.card("TestGap", "Draw 2 cards."))

    def test_unsupported_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestLiteral",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestLiteral : ModCardTemplate
{
    // RDDesign: base[0]
    private int Amount => 2;
    public TestLiteral() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            with self.assertRaisesRegex(CardDesignApplyError, "immediately followed"):
                candidate_for_card(
                    workspace, self.card("TestLiteral", "Amount 2.")
                )

    def test_constant_cannot_hide_upgrade_difference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestConstantUpgrade",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestConstantUpgrade : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0]
    private const int Amount = 2;
    public TestConstantUpgrade() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            with self.assertRaisesRegex(CardDesignApplyError, "different base and upgraded"):
                candidate_for_card(
                    workspace,
                    self.card(
                        "TestConstantUpgrade", "Amount 2.", "Amount 3."
                    ),
                )

    def test_manual_annotation_records_specific_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestManual",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestManual : ModCardTemplate
{
    // RDDesignManual: base[0], upgrade[0] - Value comes from an engine rule.
    public TestManual() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card("TestManual", "Reduce by 30%.", "Reduce by 30%."),
            )
            self.assertEqual(candidate["effects"], [])
            self.assertEqual(
                candidate["audit"]["manualNumbers"][0]["reason"],
                "Value comes from an engine rule.",
            )
            self.assertEqual(candidate["audit"]["unmappedBaseNumberIndices"], [])

    def test_missing_annotation_remains_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestMissing",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestMissing : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(2)];
    public TestMissing() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card("TestMissing", "Draw 2 cards.", "Draw 2 cards."),
            )
            self.assertEqual(candidate["effects"], [])
            self.assertEqual(candidate["audit"]["unmappedBaseNumberIndices"], [0])
            self.assertEqual(candidate["audit"]["unmappedUpgradeNumberIndices"], [0])

    def test_upgrade_only_manual_annotation_covers_upgrade_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestUpgradeOnly",
                """[RegisterCard(typeof(TestPool))]
public sealed class TestUpgradeOnly : ModCardTemplate
{
    // RDDesignManualUpgrade: upgrade[0] - Base description uses X without a number.
    public TestUpgradeOnly() : base(
        0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card("TestUpgradeOnly", "Create X cards.", "Create X+1 cards."),
            )
            manual = candidate["audit"]["manualNumbers"][0]
            self.assertEqual(manual["upgradeNumberIndex"], 0)
            self.assertNotIn("baseNumberIndex", manual)
            self.assertEqual(
                candidate["audit"]["unmappedUpgradeNumberIndices"], []
            )

    def test_ignores_numbers_embedded_in_card_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "Test54",
                """[RegisterCard(typeof(TestPool))]
public sealed class Test54 : ModCardTemplate
{
    public Test54() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                self.card("Test54", "Add a Test54.", "Add a Test54."),
            )
            self.assertEqual(candidate["effects"], [])
            self.assertEqual(candidate["audit"]["manualNumbers"], [])
            self.assertEqual(candidate["audit"]["unmappedBaseNumberIndices"], [])

    def test_deprecated_blank_description_keeps_registered_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.workspace_with_card(
                directory,
                "TestDeprecated",
                """[RegisterCard(typeof(DeprecatedCardPool))]
public sealed class TestDeprecated : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(9m, ValueProp.Move)
    ];
    public TestDeprecated() : base(
        1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy) { }
}
""",
            )
            candidate = candidate_for_card(
                workspace,
                {
                    "key": "TestDeprecated",
                    "稀有度": "弃用",
                    DESCRIPTION: None,
                    UPGRADED_DESCRIPTION: None,
                },
            )
            self.assertEqual(candidate["constructor"]["rarity"], "Common")
            self.assertEqual(candidate["effects"], [])
            self.assertEqual(candidate["audit"]["unmappedBaseNumberIndices"], [])

    def test_repository_mappings_match_current_code_and_snapshot(self) -> None:
        workspace = SCRIPTS_DIR.parent
        snapshot = json.loads(
            (workspace / "design" / "card-design-snapshots" / "current.json").read_text(
                encoding="utf-8-sig"
            )
        )
        actual = json.loads(
            (workspace / "design" / "card-design-mappings.json").read_text(
                encoding="utf-8-sig"
            )
        )
        expected = build_mapping_payload(workspace, snapshot["cards"])
        self.assertEqual(actual, expected)
        registered_keys = {
            path.stem
            for path in (workspace / "Mod" / "Cards").glob("*.cs")
            if "[RegisterCard" in path.read_text(encoding="utf-8-sig")
        }
        self.assertEqual(set(actual["cards"]), registered_keys)
        for key, mapping in actual["cards"].items():
            audit = mapping["audit"]
            self.assertEqual(audit["unmappedBaseNumberIndices"], [], key)
            self.assertEqual(audit["unmappedUpgradeNumberIndices"], [], key)
            for manual in audit["manualNumbers"]:
                reason = str(manual.get("reason") or "").strip()
                self.assertTrue(reason, key)
                self.assertNotIn("no unique automatic code target", reason)

    def test_registered_card_costs_match_current_snapshot(self) -> None:
        workspace = SCRIPTS_DIR.parent
        snapshot = json.loads(
            (workspace / "design" / "card-design-snapshots" / "current.json").read_text(
                encoding="utf-8-sig"
            )
        )
        for card in snapshot["cards"]:
            key = card["key"]
            path = workspace / "Mod" / "Cards" / f"{key}.cs"
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8-sig")
            if "[RegisterCard" not in source:
                continue
            base_cost = card.get("费用")
            upgraded_cost = card.get("升级后费用")
            if not isinstance(base_cost, int) or not isinstance(upgraded_cost, int):
                continue
            constructor_cost = _constructor_args(source, key)[0][2].strip()
            if not re.fullmatch(r"-?[0-9]+", constructor_cost):
                continue
            deltas = [
                int(value)
                for value in re.findall(
                    r"EnergyCost\.UpgradeBy\(\s*(-?[0-9]+)\s*\)",
                    source,
                )
            ]
            self.assertLessEqual(len(deltas), 1, key)
            self.assertEqual(int(constructor_cost), base_cost, key)
            self.assertEqual(int(constructor_cost) + sum(deltas), upgraded_cost, key)

    def test_block_cards_declare_gains_block(self) -> None:
        workspace = SCRIPTS_DIR.parent
        for path in (workspace / "Mod" / "Cards").glob("*.cs"):
            source = path.read_text(encoding="utf-8-sig")
            if (
                "[RegisterCard" in source
                and "new BlockVar(" in source
                and "CreatureCmd.GainBlock" in source
            ):
                self.assertIn(
                    "public override bool GainsBlock => true;",
                    source,
                    path.stem,
                )

    def test_writes_mapping_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mappings.json"
            payload = {"schemaVersion": 1, "cards": {"Test1": {"effects": []}}}
            result = write_mapping_file(path, payload)
            self.assertEqual(result, payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)
            self.assertFalse(path.with_name(".mappings.json.tmp").exists())

    def test_partial_write_merges_selected_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mappings.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "cards": {
                            "Keep": {"effects": [1]},
                            "Replace": {"effects": [2]},
                        },
                    }
                ),
                encoding="utf-8",
            )
            payload = {
                "schemaVersion": 1,
                "cards": {"Replace": {"effects": [3]}},
            }
            result = write_mapping_file(path, payload, {"Replace"})
            self.assertEqual(result["cards"]["Keep"]["effects"], [1])
            self.assertEqual(result["cards"]["Replace"]["effects"], [3])


if __name__ == "__main__":
    unittest.main()

