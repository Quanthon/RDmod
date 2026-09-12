using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test80 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(10m, ValueProp.Move), 
        // RDDesign: base[1], upgrade[1]
        new CardsVar("OutOfControlCards", 1)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromCard<OutOfControl>(), HoverTipFactory.FromCard<AppleCider>()];

    public Test80() : base(1, CardType.Attack, CardRarity.Rare, TargetType.AllEnemies) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .FromCard(this, cardPlay).TargetingAllOpponents(CombatState!).Execute(choiceContext);

        List<CardModel> outOfControlCards = [];
        for (int i = 0; i < DynamicVars["OutOfControlCards"].IntValue; i++)
            outOfControlCards.Add(CombatState!.CreateCard<OutOfControl>(Owner));
        await CardPileCmd.AddGeneratedCardsToCombat(outOfControlCards, PileType.Hand, Owner);

        int remainingSlots = CardPile.MaxCardsInHand - PileType.Hand.GetPile(Owner).Cards.Count;
        await CardGenerationOperations.AddAppleCidersToHand(
            this,
            remainingSlots);
    }

    protected override void OnUpgrade() => DynamicVars.Damage.UpgradeValueBy(4m);
}
