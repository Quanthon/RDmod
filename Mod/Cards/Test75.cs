using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using STS2RitsuLib.Cards.DynamicVars;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test75 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int FlightPerEnergyGain = 2;
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    public override IEnumerable<CardKeyword> CanonicalKeywords =>
    [
        CardKeyword.Exhaust
    ];

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[1], upgrade[1]
        new EnergyVar(1),
        ModCardVars.Computed(
            "CalculatedEnergy",
            0,
            card => card?.Owner.PlayerCombatState is null
                ? 0
                : Math.Max(card.Owner.Creature.GetPower<FlightPower>()?.Amount ?? 0, 0)
                    / FlightPerEnergyGain * card.DynamicVars.Energy.IntValue)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Flight, EnergyHoverTip];

    public Test75() : base(0, CardType.Skill, CardRarity.Rare, TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        int flight = Math.Max(Owner.Creature.GetPower<FlightPower>()?.Amount ?? 0, 0);
        int triggerCount = flight / FlightPerEnergyGain;
        if (triggerCount > 0)
            await PlayerCmd.GainEnergy(DynamicVars.Energy.IntValue * triggerCount, Owner);
    }

    protected override void OnUpgrade()
    {
        AddKeyword(CardKeyword.Retain);
    }
}
