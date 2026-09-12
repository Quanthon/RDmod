using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class DaringDoTreasure : ModCardTemplate
{
    public override bool CanBeGeneratedInCombat => false;
    public override bool CanBeGeneratedByModifiers => false;
    public override CardAssetProfile AssetProfile => new(PortraitPath: "res://RDMod/images/cards/DaringDoTreasure.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("GoldPercent", 100m),
        new PowerVar<DaringDoTreasurePower>(1m)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [HoverTipFactory.FromPower<DaringDoTreasurePower>()];
    public DaringDoTreasure() : base(2, CardType.Power, CardRarity.Token, TargetType.Self) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        DaringDoTreasurePower? power = await PowerCmd.Apply<DaringDoTreasurePower>(choiceContext, Owner.Creature,
            DynamicVars["DaringDoTreasurePower"].BaseValue, Owner.Creature, this);
        power?.AddGoldPercent(DynamicVars["GoldPercent"].BaseValue);
    }

    protected override void OnUpgrade()
    {
        EnergyCost.UpgradeBy(-2);
        DynamicVars["GoldPercent"].UpgradeValueBy(100m);
    }
}
