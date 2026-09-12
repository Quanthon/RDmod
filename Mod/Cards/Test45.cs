using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test45 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<FlightPower>(3m),
        // RDDesign: base[1], upgrade[1]
        new PowerVar<StrengthPower>(2m)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
    [
        RDmod.Mechanics.KeywordHoverTips.Flight,
        HoverTipFactory.FromPower<FlightStrengthPower>(DynamicVars.Strength.IntValue),
        HoverTipFactory.FromPower<StrengthPower>(DynamicVars.Strength.IntValue)
    ];

    public Test45() : base(2, CardType.Power, CardRarity.Uncommon, TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        await PowerCmd.Apply<FlightStrengthPower>(
            choiceContext,
            Owner.Creature,
            DynamicVars.Strength.BaseValue,
            Owner.Creature,
            this
        );
        await PowerCmd.Apply<FlightPower>(
            choiceContext,
            Owner.Creature,
            DynamicVars["FlightPower"].BaseValue,
            Owner.Creature,
            this
        );
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Strength.UpgradeValueBy(1m);
    }
}
