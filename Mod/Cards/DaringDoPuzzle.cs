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
public sealed class DaringDoPuzzle : ModCardTemplate
{
    public override bool CanBeGeneratedInCombat => false;
    public override bool CanBeGeneratedByModifiers => false;
    public override CardAssetProfile AssetProfile => new(PortraitPath: "res://RDMod/images/cards/DaringDoPuzzle.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override bool ShouldGlowGoldInternal =>
        CombatState is not null && HasMatchingCosts(OtherPlayableHandCards());

    private List<CardModel> OtherPlayableHandCards() =>
        PileType.Hand.GetPile(Owner).Cards
            .Where(card => card != this && !card.Keywords.Contains(CardKeyword.Unplayable)).ToList();

    private static bool HasMatchingCosts(IReadOnlyCollection<CardModel> cards)
    {
        int distinctCosts = cards.Select(card =>
            (card.EnergyCost.CostsX, card.EnergyCost.GetWithModifiers(CostModifiers.All))).Distinct().Count();
        return distinctCosts == 1 || distinctCosts == cards.Count;
    }

    public DaringDoPuzzle() : base(0, CardType.Skill, CardRarity.Token, TargetType.Self) { }
    protected override void OnUpgrade() => AddKeyword(CardKeyword.Retain);

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        // Freeze current costs and the original hand; cards drawn during autoplay are not added.
        List<CardModel> cards = OtherPlayableHandCards();
        if (!HasMatchingCosts(cards))
            return;
        foreach (CardModel card in cards)
        {
            if (card.Pile?.Type == PileType.Hand)
                await CardCmd.AutoPlay(choiceContext, card, null);
        }
    }
}
