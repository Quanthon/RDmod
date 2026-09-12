"""Registered atomic effect templates used by the card scaffold."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Iterator


class TemplateRegistryError(ValueError):
    """Raised when effect templates are invalid or ambiguous."""


@dataclass(frozen=True)
class Effect:
    template_id: str
    kind: str
    value: int
    label: str
    var_name: str
    power_type: str | None = None


@dataclass(frozen=True)
class EffectSequence:
    """An ordered list of independently parsed atomic effects."""

    effects: tuple[Effect, ...]

    def __iter__(self) -> Iterator[Effect]:
        return iter(self.effects)

    def __len__(self) -> int:
        return len(self.effects)


@dataclass(frozen=True)
class ConditionalEffect:
    """Reserved composition node for a condition wrapping another effect."""

    condition: str
    effect: Effect | EffectSequence


@dataclass(frozen=True)
class TriggeredEffect:
    """Reserved composition node for an effect resolved at another timing."""

    trigger: str
    effect: Effect | EffectSequence


class EffectTemplate(ABC):
    """Complete scaffold behavior for one recognized atomic effect."""

    template_id: str
    kind: str
    pattern: re.Pattern[str]
    gains_block = False
    target: str | None = None
    requires_hover = False
    requires_value_props = False
    requires_powers = False

    def match(self, segment: str) -> Effect | None:
        match = self.pattern.fullmatch(segment)
        if match is None:
            return None
        return self.create_effect(segment, match)

    @abstractmethod
    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        raise NotImplementedError

    @abstractmethod
    def dynamic_var_line(self, effect: Effect) -> str | None:
        raise NotImplementedError

    def hover_tip_line(self, effect: Effect) -> str | None:
        return None

    def keyword_line(self, effect: Effect) -> str | None:
        return None

    @abstractmethod
    def play_lines(self, effect: Effect) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def upgrade_line(self, effect: Effect, delta: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def localization_line(self, effect: Effect) -> str:
        raise NotImplementedError

    def shape_key(self, effect: Effect) -> tuple[str, str]:
        return self.template_id, effect.var_name


class TemplateRegistry:
    """Ordered registry that rejects duplicate IDs and ambiguous matches."""

    def __init__(self, templates: Iterable[EffectTemplate] = ()) -> None:
        self._templates: list[EffectTemplate] = []
        self._by_id: dict[str, EffectTemplate] = {}
        for template in templates:
            self.register(template)

    @property
    def templates(self) -> tuple[EffectTemplate, ...]:
        return tuple(self._templates)

    def register(self, template: EffectTemplate) -> None:
        if template.template_id in self._by_id:
            raise TemplateRegistryError(
                f"Duplicate effect template ID: {template.template_id}"
            )
        self._templates.append(template)
        self._by_id[template.template_id] = template

    def get(self, template_id: str) -> EffectTemplate:
        try:
            return self._by_id[template_id]
        except KeyError as exc:
            raise TemplateRegistryError(
                f"Unknown effect template ID: {template_id}"
            ) from exc

    def match(self, segment: str) -> Effect | None:
        matches = [
            effect
            for template in self._templates
            if (effect := template.match(segment)) is not None
        ]
        if len(matches) > 1:
            ids = ", ".join(effect.template_id for effect in matches)
            raise TemplateRegistryError(
                f"Ambiguous effect segment {segment!r}; matched: {ids}"
            )
        return matches[0] if matches else None


class DamageTemplate(EffectTemplate):
    template_id = "direct_damage"
    kind = "damage"
    pattern = re.compile(r"造成([0-9]+)点伤害")
    target = "AnyEnemy"
    requires_value_props = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, int(match.group(1)), segment, "Damage"
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new DamageVar({effect.value}m, ValueProp.Move)"

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await DamageCmd.Attack(DynamicVars.Damage.BaseValue)",
            "    .FromCard(this, cardPlay)",
            "    .Targeting(cardPlay.Target)",
            '    .WithHitFx("vfx/vfx_attack_slash")',
            "    .Execute(choiceContext);",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f"DynamicVars.Damage.UpgradeValueBy({delta}m);"

    def localization_line(self, effect: Effect) -> str:
        return "造成{Damage:diff()}点伤害。"


class SlyKeywordTemplate(EffectTemplate):
    template_id = "native_sly"
    kind = "keyword"
    pattern = re.compile(r"奇巧")

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, 0, segment, "Sly"
        )

    def dynamic_var_line(self, effect: Effect) -> None:
        return None

    def keyword_line(self, effect: Effect) -> str:
        return "CardKeyword.Sly"

    def play_lines(self, effect: Effect) -> list[str]:
        return []

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        raise ValueError("Sly has no numeric upgrade.")

    def localization_line(self, effect: Effect) -> str:
        return ""


class BlockTemplate(EffectTemplate):
    template_id = "gain_block"
    kind = "block"
    pattern = re.compile(r"获得([0-9]+)点格挡")
    gains_block = True
    requires_value_props = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, int(match.group(1)), segment, "Block"
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new BlockVar({effect.value}m, ValueProp.Move)"

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await CreatureCmd.GainBlock(Owner.Creature, DynamicVars.Block, cardPlay);"
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f"DynamicVars.Block.UpgradeValueBy({delta}m);"

    def localization_line(self, effect: Effect) -> str:
        return "获得{Block:diff()}点[gold]格挡[/gold]。"


class DrawTemplate(EffectTemplate):
    template_id = "draw_cards"
    kind = "draw"
    pattern = re.compile(r"抽([0-9]+)张牌")

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, int(match.group(1)), segment, "Cards"
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new CardsVar({effect.value})"

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await CardPileCmd.Draw(choiceContext, DynamicVars.Cards.BaseValue, Owner);"
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f"DynamicVars.Cards.UpgradeValueBy({delta}m);"

    def localization_line(self, effect: Effect) -> str:
        return "抽{Cards:diff()}张牌。"


class EnergyTemplate(EffectTemplate):
    template_id = "gain_energy"
    kind = "energy"
    pattern = re.compile(r"获得(?:\[)?([0-9]+)(?:点)?能量(?:\])?")
    requires_hover = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, int(match.group(1)), segment, "Energy"
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new EnergyVar({effect.value})"

    def hover_tip_line(self, effect: Effect) -> str:
        return "EnergyHoverTip"

    def play_lines(self, effect: Effect) -> list[str]:
        return ["await PlayerCmd.GainEnergy(DynamicVars.Energy.IntValue, Owner);"]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f"DynamicVars.Energy.UpgradeValueBy({delta}m);"

    def localization_line(self, effect: Effect) -> str:
        return "获得{Energy:energyIcons()}。"


class GainPowerTemplate(EffectTemplate):
    kind = "power"
    requires_hover = True
    requires_powers = True

    def __init__(
        self, template_id: str, label: str, power_type: str, var_name: str
    ) -> None:
        self.label = label
        self.power_type = power_type
        self.var_name = var_name
        self.template_id = template_id
        self.pattern = re.compile(rf"获得([0-9]+)层{re.escape(label)}")

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id,
            self.kind,
            int(match.group(1)),
            self.label,
            self.var_name,
            self.power_type,
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new PowerVar<{effect.power_type}>({effect.value}m)"

    def hover_tip_line(self, effect: Effect) -> str:
        return (
            f'HoverTipFactory.FromPower<{effect.power_type}>('
            f'DynamicVars["{effect.var_name}"].IntValue)'
        )

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            f"await PowerCmd.Apply<{effect.power_type}>(",
            "    choiceContext,",
            "    Owner.Creature,",
            f'    DynamicVars["{effect.var_name}"].BaseValue,',
            "    Owner.Creature,",
            "    this",
            ");",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f'DynamicVars["{effect.var_name}"].UpgradeValueBy({delta}m);'

    def localization_line(self, effect: Effect) -> str:
        return f"获得{{{effect.var_name}:diff()}}层[gold]{effect.label}[/gold]。"


class FirstFlightEnergyTemplate(EffectTemplate):
    template_id = "first_flight_energy_per_turn"
    kind = "triggered_power"
    pattern = re.compile(r"每回合第一次获得飞行时，获得\[([0-9]+)能量\]")
    requires_hover = True
    requires_powers = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, int(match.group(1)), segment, "Energy"
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new EnergyVar({effect.value})"

    def hover_tip_line(self, effect: Effect) -> str:
        return (
            "HoverTipFactory.FromPower<FirstFlightEnergyPower>("
            "DynamicVars.Energy.IntValue)"
        )

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await PowerCmd.Apply<FirstFlightEnergyPower>(",
            "    choiceContext,",
            "    Owner.Creature,",
            "    DynamicVars.Energy.BaseValue,",
            "    Owner.Creature,",
            "    this",
            ");",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return f"DynamicVars.Energy.UpgradeValueBy({delta}m);"

    def localization_line(self, effect: Effect) -> str:
        return (
            "每回合第一次获得[gold]飞行[/gold]时，"
            "获得{Energy:energyIcons()}。"
        )


class TurnPreparationTemplate(EffectTemplate):
    template_id = "gain_preparation_at_turn_start"
    kind = "triggered_power"
    pattern = re.compile(r"在你的回合开始时，获得([0-9]+)层蓄力")
    requires_hover = True
    requires_powers = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id,
            self.kind,
            int(match.group(1)),
            segment,
            "TurnPreparationPower",
            "TurnPreparationPower",
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new PowerVar<TurnPreparationPower>({effect.value}m)"

    def hover_tip_line(self, effect: Effect) -> str:
        return (
            "HoverTipFactory.FromPower<TurnPreparationPower>("
            'DynamicVars["TurnPreparationPower"].IntValue)'
        )

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await PowerCmd.Apply<TurnPreparationPower>(",
            "    choiceContext,",
            "    Owner.Creature,",
            '    DynamicVars["TurnPreparationPower"].BaseValue,',
            "    Owner.Creature,",
            "    this",
            ");",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return (
            'DynamicVars["TurnPreparationPower"]'
            f".UpgradeValueBy({delta}m);"
        )

    def localization_line(self, effect: Effect) -> str:
        return (
            "在你的回合开始时，获得"
            "{TurnPreparationPower:diff()}层[gold]蓄力[/gold]。"
        )


class FlightStrengthTemplate(EffectTemplate):
    template_id = "strength_while_flying"
    kind = "conditional_power"
    pattern = re.compile(r"当你拥有飞行时，获得([0-9]+)点力量")
    requires_hover = True
    requires_powers = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id,
            self.kind,
            int(match.group(1)),
            segment,
            "FlightStrengthPower",
            "FlightStrengthPower",
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new PowerVar<FlightStrengthPower>({effect.value}m)"

    def hover_tip_line(self, effect: Effect) -> str:
        return (
            "HoverTipFactory.FromPower<FlightStrengthPower>("
            'DynamicVars["FlightStrengthPower"].IntValue)'
        )

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await PowerCmd.Apply<FlightStrengthPower>(",
            "    choiceContext,",
            "    Owner.Creature,",
            '    DynamicVars["FlightStrengthPower"].BaseValue,',
            "    Owner.Creature,",
            "    this",
            ");",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        return (
            'DynamicVars["FlightStrengthPower"]'
            f".UpgradeValueBy({delta}m);"
        )

    def localization_line(self, effect: Effect) -> str:
        return (
            "当你拥有[gold]飞行[/gold]时，获得"
            "{FlightStrengthPower:diff()}点[gold]力量[/gold]。"
        )


class DoublePreparationTemplate(EffectTemplate):
    template_id = "double_preparation"
    kind = "modify_power"
    pattern = re.compile(r"你的蓄力层数翻倍")
    requires_hover = True
    requires_powers = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id, self.kind, 0, segment, "", "PreparationPower"
        )

    def dynamic_var_line(self, effect: Effect) -> None:
        return None

    def hover_tip_line(self, effect: Effect) -> str:
        return "HoverTipFactory.FromPower<PreparationPower>()"

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "PreparationPower? preparation = Owner.Creature.GetPower<PreparationPower>();",
            "if (preparation is not null && preparation.Amount > 0)",
            "{",
            "    await PowerCmd.ModifyAmount(",
            "        choiceContext,",
            "        preparation,",
            "        preparation.Amount,",
            "        Owner.Creature,",
            "        this",
            "    );",
            "}",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        raise ValueError("Double preparation has no numeric upgrade.")

    def localization_line(self, effect: Effect) -> str:
        return "你的[gold]蓄力[/gold]层数翻倍。"


class PreserveFlightTemplate(EffectTemplate):
    template_id = "preserve_flight_until_next_turn_end"
    kind = "timed_power"
    pattern = re.compile(r"在你的下一回合结束前，飞行层数不会减少")
    requires_hover = True
    requires_powers = True

    def create_effect(self, segment: str, match: re.Match[str]) -> Effect:
        return Effect(
            self.template_id,
            self.kind,
            2,
            segment,
            "FlightPreservationPower",
            "FlightPreservationPower",
        )

    def dynamic_var_line(self, effect: Effect) -> str:
        return f"new PowerVar<FlightPreservationPower>({effect.value}m)"

    def hover_tip_line(self, effect: Effect) -> str:
        return "HoverTipFactory.FromPower<FlightPreservationPower>()"

    def play_lines(self, effect: Effect) -> list[str]:
        return [
            "await PowerCmd.Apply<FlightPreservationPower>(",
            "    choiceContext,",
            "    Owner.Creature,",
            '    DynamicVars["FlightPreservationPower"].BaseValue,',
            "    Owner.Creature,",
            "    this",
            ");",
        ]

    def upgrade_line(self, effect: Effect, delta: int) -> str:
        raise ValueError("Flight preservation duration does not upgrade.")

    def localization_line(self, effect: Effect) -> str:
        return (
            "在你的下一回合结束前，[gold]飞行[/gold]层数不会减少。"
        )


EFFECT_TEMPLATES = TemplateRegistry(
    (
        DamageTemplate(),
        SlyKeywordTemplate(),
        BlockTemplate(),
        DrawTemplate(),
        EnergyTemplate(),
        GainPowerTemplate("gain_flight", "飞行", "FlightPower", "FlightPower"),
        GainPowerTemplate(
            "gain_preparation",
            "蓄力",
            "PreparationPower",
            "PreparationPower",
        ),
        FirstFlightEnergyTemplate(),
        TurnPreparationTemplate(),
        FlightStrengthTemplate(),
        DoublePreparationTemplate(),
        PreserveFlightTemplate(),
    )
)

from card_effect_templates_section8 import register_section8_templates


register_section8_templates(EFFECT_TEMPLATES, EffectTemplate, Effect)
