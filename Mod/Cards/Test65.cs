using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test65 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromCard<AppleCider>(), HoverTipFactory.Static(StaticHoverTip.Transform)];

    public Test65() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        List<CardModel> statuses = PileType.Hand.GetPile(Owner).Cards
            .Where(card => card.Type == CardType.Status && card.IsTransformable)
            .ToList();

        foreach (CardModel status in statuses)
            await CardCmd.Transform(status, CombatState!.CreateCard<AppleCider>(Owner));
    }

    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}
