using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test60 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int DiscardDiscount = 1;
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public Test60() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) =>
        await PowerCmd.Apply<DiscardedCardDiscountPower>(choiceContext, Owner.Creature, DiscardDiscount, Owner.Creature, this);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}
