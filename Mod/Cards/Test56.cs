using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
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
public sealed class Test56 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(5m, ValueProp.Move),
        ModCardVars.Computed("CalculatedCardsDrawn", 0, CalculatedCardsDrawn),
        ModCardVars.Computed("CalculatedHits", 0, CalculatedHits)
    ];

    public Test56() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        ArgumentNullException.ThrowIfNull(cardPlay.Target);
        List<CardModel> statuses = Owner.PlayerCombatState!.AllCards
            .Where(card => card.Type == CardType.Status)
            .ToList();
        await CardPileCmd.Add(statuses, PileType.Hand);

        int hitCount = PileType.Hand.GetPile(Owner).Cards.Count(
            card => card.Type == CardType.Status);
        if (hitCount == 0)
            return;

        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .WithHitCount(hitCount)
            .FromCard(this, cardPlay)
            .Targeting(cardPlay.Target)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(choiceContext);
    }

    protected override void OnUpgrade() => DynamicVars.Damage.UpgradeValueBy(2m);

    private static decimal CalculatedHits(CardModel? card)
    {
        (int cardsDrawn, int statusesInHand) = CalculatedCounts(card);
        return statusesInHand + cardsDrawn;
    }

    private static decimal CalculatedCardsDrawn(CardModel? card) =>
        CalculatedCounts(card).cardsDrawn;

    private static (int cardsDrawn, int statusesInHand) CalculatedCounts(
        CardModel? card)
    {
        if (card?.Owner.PlayerCombatState is null)
            return (0, 0);

        IReadOnlyList<CardModel> hand = PileType.Hand.GetPile(card.Owner).Cards;
        int statusesInHand = hand.Count(handCard => handCard.Type == CardType.Status);
        int otherCardsInHand = hand.Count(handCard => handCard != card);
        int availableSlots = Math.Max(CardPile.MaxCardsInHand - otherCardsInHand, 0);
        int statusesOutsideHand = card.Owner.PlayerCombatState.AllCards.Count(
            status => status.Type == CardType.Status && status.Pile?.Type != PileType.Hand);
        return (
            Math.Min(statusesOutsideHand, availableSlots),
            statusesInHand);
    }
}
