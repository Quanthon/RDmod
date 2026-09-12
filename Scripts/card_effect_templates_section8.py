"""Stable basic-effect templates verified by the section 8 card batch."""

from __future__ import annotations

import re


def register_section8_templates(registry, effect_template_type, effect_type) -> None:
    """Register conservative templates without coupling this module to the registry."""

    class StandardKeywordTemplate(effect_template_type):
        kind = "keyword"

        def __init__(self, template_id: str, label: str, keyword: str) -> None:
            self.template_id = template_id
            self.pattern = re.compile(re.escape(label))
            self.keyword = keyword

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id, self.kind, 0, segment, self.keyword
            )

        def dynamic_var_line(self, effect):
            return None

        def keyword_line(self, effect):
            return f"CardKeyword.{self.keyword}"

        def play_lines(self, effect):
            return []

        def upgrade_line(self, effect, delta):
            raise ValueError(f"{self.keyword} has no numeric upgrade.")

        def localization_line(self, effect):
            return ""

    class MultiHitDamageTemplate(effect_template_type):
        template_id = "multi_hit_damage"
        kind = "damage"
        pattern = re.compile(r"造成([0-9]+)点伤害([0-9]+)次")
        target = "AnyEnemy"
        requires_value_props = True

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id,
                self.kind,
                int(match.group(1)),
                match.group(2),
                "Damage",
            )

        def dynamic_var_line(self, effect):
            return (
                f"new DamageVar({effect.value}m, ValueProp.Move),\n"
                f"        new RepeatVar({int(effect.label)})"
            )

        def play_lines(self, effect):
            return [
                "await DamageCmd.Attack(DynamicVars.Damage.BaseValue)",
                "    .WithHitCount(DynamicVars.Repeat.IntValue)",
                "    .FromCard(this, cardPlay)",
                "    .Targeting(cardPlay.Target)",
                '    .WithHitFx("vfx/vfx_attack_slash")',
                "    .Execute(choiceContext);",
            ]

        def upgrade_line(self, effect, delta):
            return f"DynamicVars.Damage.UpgradeValueBy({delta}m);"

        def localization_line(self, effect):
            return "造成{Damage:diff()}点伤害{Repeat:diff()}次。"

        def shape_key(self, effect):
            return self.template_id, f"{effect.var_name}:{effect.label}"

    class RepeatedSelfDamageTemplate(effect_template_type):
        template_id = "repeated_card_self_damage"
        kind = "self_damage"
        pattern = re.compile(r"你受到([0-9]+)点伤害([0-9]+)次")
        requires_value_props = True

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id,
                self.kind,
                int(match.group(1)),
                match.group(2),
                "SelfDamage",
            )

        def dynamic_var_line(self, effect):
            return (
                f'new DamageVar("SelfDamage", {effect.value}m, '
                "ValueProp.Unblockable | ValueProp.Unpowered | ValueProp.Move),\n"
                f'        new RepeatVar("SelfDamageRepeat", {int(effect.label)})'
            )

        def play_lines(self, effect):
            return [
                'for (int i = 0; i < DynamicVars["SelfDamageRepeat"].IntValue; i++)',
                "{",
                "    await CreatureCmd.Damage(choiceContext, Owner.Creature,",
                '        (DamageVar)DynamicVars["SelfDamage"], this, cardPlay);',
                "}",
            ]

        def upgrade_line(self, effect, delta):
            return f'DynamicVars["SelfDamage"].UpgradeValueBy({delta}m);'

        def localization_line(self, effect):
            return (
                "你受到{SelfDamage:diff()}点伤害"
                "{SelfDamageRepeat:diff()}次。"
            )

        def shape_key(self, effect):
            return self.template_id, f"{effect.var_name}:{effect.label}"

    class ConditionalPreparationDrawTemplate(effect_template_type):
        template_id = "draw_with_preparation"
        kind = "conditional_draw"
        pattern = re.compile(r"如果你拥有蓄力，抽([0-9]+)张牌")
        requires_hover = True
        requires_powers = True

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id, self.kind, int(match.group(1)), segment, "Cards"
            )

        def dynamic_var_line(self, effect):
            return f"new CardsVar({effect.value})"

        def hover_tip_line(self, effect):
            return "HoverTipFactory.FromPower<PreparationPower>()"

        def play_lines(self, effect):
            return [
                "if (Owner.Creature.GetPower<PreparationPower>() is { Amount: > 0 })",
                "{",
                "    await CardPileCmd.Draw(",
                "        choiceContext, DynamicVars.Cards.IntValue, Owner);",
                "}",
            ]

        def upgrade_line(self, effect, delta):
            return f"DynamicVars.Cards.UpgradeValueBy({delta}m);"

        def localization_line(self, effect):
            return (
                "如果你拥有[gold]蓄力[/gold]，"
                "抽{Cards:diff()}张牌。"
            )

    class ConditionalFlightVulnerableTemplate(effect_template_type):
        template_id = "vulnerable_before_damage_with_flight"
        kind = "conditional_power"
        pattern = re.compile(r"如果你拥有飞行，先给予([0-9]+)层易伤")
        target = "AnyEnemy"
        requires_hover = True
        requires_powers = True
        power_type = "MegaCrit.Sts2.Core.Models.Powers.VulnerablePower"

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id,
                self.kind,
                int(match.group(1)),
                segment,
                "VulnerablePower",
                self.power_type,
            )

        def dynamic_var_line(self, effect):
            return f"new PowerVar<{self.power_type}>({effect.value}m)"

        def hover_tip_line(self, effect):
            return (
                "HoverTipFactory.FromPower<FlightPower>(),\n"
                f"        HoverTipFactory.FromPower<{self.power_type}>()"
            )

        def play_lines(self, effect):
            return [
                "if (Owner.Creature.GetPower<FlightPower>() is { Amount: > 0 })",
                "{",
                f"    await PowerCmd.Apply<{self.power_type}>(",
                "        choiceContext, cardPlay.Target,",
                '        DynamicVars["VulnerablePower"].BaseValue,',
                "        Owner.Creature, this);",
                "}",
            ]

        def upgrade_line(self, effect, delta):
            return f'DynamicVars["VulnerablePower"].UpgradeValueBy({delta}m);'

        def localization_line(self, effect):
            return (
                "如果你拥有[gold]飞行[/gold]，先给予"
                "{VulnerablePower:diff()}层[gold]易伤[/gold]。"
            )

    class ConditionalPreparationWeakTemplate(effect_template_type):
        template_id = "weak_with_preparation"
        kind = "conditional_power"
        pattern = re.compile(r"如果你拥有蓄力，给予([0-9]+)层虚弱")
        target = "AnyEnemy"
        requires_hover = True
        requires_powers = True
        power_type = "MegaCrit.Sts2.Core.Models.Powers.WeakPower"

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id,
                self.kind,
                int(match.group(1)),
                segment,
                "WeakPower",
                self.power_type,
            )

        def dynamic_var_line(self, effect):
            return f"new PowerVar<{self.power_type}>({effect.value}m)"

        def hover_tip_line(self, effect):
            return (
                "HoverTipFactory.FromPower<PreparationPower>(),\n"
                f"        HoverTipFactory.FromPower<{self.power_type}>()"
            )

        def play_lines(self, effect):
            return [
                "if (Owner.Creature.GetPower<PreparationPower>() is { Amount: > 0 })",
                "{",
                f"    await PowerCmd.Apply<{self.power_type}>(",
                "        choiceContext, cardPlay.Target,",
                '        DynamicVars["WeakPower"].BaseValue,',
                "        Owner.Creature, this);",
                "}",
            ]

        def upgrade_line(self, effect, delta):
            return f'DynamicVars["WeakPower"].UpgradeValueBy({delta}m);'

        def localization_line(self, effect):
            return (
                "如果你拥有[gold]蓄力[/gold]，给予"
                "{WeakPower:diff()}层[gold]虚弱[/gold]。"
            )

    class GenerateOutOfControlTemplate(effect_template_type):
        template_id = "generate_out_of_control_to_hand"
        kind = "generate_card"
        pattern = re.compile(r"将一张失控加入你的手牌")
        requires_hover = True

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id, self.kind, 1, segment, "GeneratedOutOfControl"
            )

        def dynamic_var_line(self, effect):
            return None

        def hover_tip_line(self, effect):
            return "HoverTipFactory.FromCard<OutOfControl>()"

        def play_lines(self, effect):
            return [
                "await CardPileCmd.AddGeneratedCardToCombat(",
                "    CombatState!.CreateCard<OutOfControl>(Owner),",
                "    PileType.Hand, Owner);",
            ]

        def upgrade_line(self, effect, delta):
            raise ValueError("Generated OutOfControl count does not upgrade.")

        def localization_line(self, effect):
            return "将一张[gold]失控[/gold]加入你的手牌。"

    class AllEnemiesDamageTemplate(effect_template_type):
        template_id = "all_enemies_damage"
        kind = "damage"
        pattern = re.compile(r"对所有敌人造成([0-9]+)点伤害")
        target = "AllEnemies"
        requires_value_props = True

        def create_effect(self, segment, match):
            return effect_type(
                self.template_id, self.kind, int(match.group(1)), segment, "Damage"
            )

        def dynamic_var_line(self, effect):
            return f"new DamageVar({effect.value}m, ValueProp.Move)"

        def play_lines(self, effect):
            return [
                "await DamageCmd.Attack(DynamicVars.Damage.BaseValue)",
                "    .FromCard(this, cardPlay)",
                "    .TargetingAllOpponents(CombatState!)",
                "    .Execute(choiceContext);",
            ]

        def upgrade_line(self, effect, delta):
            return f"DynamicVars.Damage.UpgradeValueBy({delta}m);"

        def localization_line(self, effect):
            return "对所有敌人造成{Damage:diff()}点伤害。"

    templates = (
        StandardKeywordTemplate("exhaust", "消耗", "Exhaust"),
        StandardKeywordTemplate("retain", "保留", "Retain"),
        StandardKeywordTemplate("innate", "固有", "Innate"),
        MultiHitDamageTemplate(),
        RepeatedSelfDamageTemplate(),
        ConditionalPreparationDrawTemplate(),
        ConditionalFlightVulnerableTemplate(),
        ConditionalPreparationWeakTemplate(),
        GenerateOutOfControlTemplate(),
        AllEnemiesDamageTemplate(),
    )
    for template in templates:
        registry.register(template)
