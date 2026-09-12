using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test68 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("PreparationThreshold", 10m),
        // RDDesign: base[1], upgrade[1]
        new DynamicVar("PreparationCost", 10m),
        // RDDesign: base[2], upgrade[2]
        new DynamicVar("DamagePerStack", 50m),
        // RDDesign: base[3], upgrade[3]
        new EnergyVar(5)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation, EnergyHoverTip];

    public Test68() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await PowerCmd.Apply<Test68Power>(
            choiceContext, Owner.Creature, 1m, Owner.Creature, this);
        Test68Power power = Owner.Creature.GetPower<Test68Power>()
            ?? throw new InvalidOperationException("Double Rainboom power was not applied.");
        power.Configure(
            DynamicVars["PreparationThreshold"].IntValue,
            DynamicVars["PreparationCost"].IntValue,
            DynamicVars["DamagePerStack"].BaseValue,
            DynamicVars.Energy.IntValue);
        await power.ResolvePreparation(choiceContext);
    }

    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}
