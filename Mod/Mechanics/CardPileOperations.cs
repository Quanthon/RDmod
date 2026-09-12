using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace RDmod.Mechanics;

public static class CardPileOperations
{
    public static IEnumerable<CardModel> HandExcept(Player owner, CardModel source) =>
        PileType.Hand.GetPile(owner).Cards.Where(card => card != source);

    public static async Task<IReadOnlyList<CardModel>> DrawMatching(
        PlayerChoiceContext choiceContext,
        Player owner,
        int count,
        Func<CardModel, bool> predicate)
    {
        List<CardModel> drawn = [];
        CardPile drawPile = PileType.Draw.GetPile(owner);

        while (drawn.Count < count &&
               PileType.Hand.GetPile(owner).Cards.Count < CardPile.MaxCardsInHand)
        {
            CardModel? next = drawPile.Cards.FirstOrDefault(predicate);
            if (next is null)
                break;

            drawPile.MoveToTopInternal(next);
            CardModel? drawnCard = await CardPileCmd.Draw(choiceContext, owner);
            if (drawnCard is null)
                break;

            drawn.Add(drawnCard);
        }

        return drawn;
    }
}
