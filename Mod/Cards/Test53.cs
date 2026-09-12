using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test53 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int EnergyThreshold = 7;

    private bool HasMetEnergyThreshold =>
        CardTurnStatistics.EnergyValuePlayedThisTurn(this) >= EnergyThreshold;

    protected override bool ShouldGlowGoldInternal => HasMetEnergyThreshold;
    protected override bool ShouldGlowRedInternal => !HasMetEnergyThreshold;

    public LocString UnplayableMessage =>
        new("cards", "RD_MOD_CARD_TEST53.unplayableMessage");

    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[1], upgrade[1]
        new DamageVar(50m, ValueProp.Move),
        // RDDesign: base[2], upgrade[2]
        new EnergyVar(5),
        ModCardVars.Computed(
            "EnergyTotal",
            0,
            card => card is null
                ? 0
                : CardTurnStatistics.EnergyValuePlayedThisTurn(card))
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [EnergyHoverTip];

    public Test53() : base(
        0,
        CardType.Attack,
        CardRarity.Rare,
        TargetType.AllEnemies)
    {
    }

    public override bool ShouldPlay(CardModel card, AutoPlayType _) =>
        !ReferenceEquals(card, this) || HasMetEnergyThreshold;

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        if (!HasMetEnergyThreshold)
            return;

        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .FromCard(this, cardPlay)
            .TargetingAllOpponents(CombatState!)
            .Execute(choiceContext);
        await PlayerCmd.GainEnergy(DynamicVars.Energy.IntValue, Owner);
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(10m);
        DynamicVars.Energy.UpgradeValueBy(1m);
    }
}