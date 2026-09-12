using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using RDmod.Mechanics;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test30 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new CardsVar(1),
        ModCardVars.Computed("CalculatedCards", 0, CalculateCardsDrawn)
    ];

    public Test30() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        int currentEnergy = Owner.PlayerCombatState!.Energy;
        await CardPileOperations.DrawMatching(
            choiceContext,
            Owner,
            DynamicVars.Cards.IntValue,
            card => !card.EnergyCost.CostsX &&
                    card.EnergyCost.GetWithModifiers(CostModifiers.All) > currentEnergy
        );
    }

    protected override void OnUpgrade() => DynamicVars.Cards.UpgradeValueBy(1m);

    private static decimal CalculateCardsDrawn(CardModel? card)
    {
        if (card?.Owner.PlayerCombatState is null)
            return 0;

        int currentEnergy = card.Owner.PlayerCombatState.Energy;
        int matchingCards = PileType.Draw.GetPile(card.Owner).Cards.Count(
            candidate => !candidate.EnergyCost.CostsX &&
                candidate.EnergyCost.GetWithModifiers(CostModifiers.All) > currentEnergy);
        int otherCardsInHand = PileType.Hand.GetPile(card.Owner).Cards.Count(
            candidate => candidate != card);
        int availableSlots = Math.Max(
            CardPile.MaxCardsInHand - otherCardsInHand,
            0);
        return Math.Min(
            card.DynamicVars.Cards.IntValue,
            Math.Min(matchingCards, availableSlots));
    }
}
