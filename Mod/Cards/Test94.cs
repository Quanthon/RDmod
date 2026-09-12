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
public sealed class Test94 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: "res://RDMod/images/cards/Test94.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<StatusDrawPower>(1m)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [HoverTipFactory.FromPower<StatusDrawPower>()];
    public Test94() : base(1, CardType.Power, CardRarity.Rare, TargetType.Self) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) =>
        await PowerCmd.Apply<StatusDrawPower>(choiceContext, Owner.Creature, DynamicVars["StatusDrawPower"].BaseValue, Owner.Creature, this);
    protected override void OnUpgrade() => DynamicVars["StatusDrawPower"].UpgradeValueBy(1m);
}
