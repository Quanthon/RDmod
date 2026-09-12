using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace RDmod.Mechanics;

public static class CardSelectionOperations
{
    public static async Task DiscardFromHand(
        PlayerChoiceContext choiceContext,
        Player player,
        int count,
        CardModel source)
    {
        if (count <= 0)
            return;

        var selected = await CardSelectCmd.FromHandForDiscard(
            choiceContext,
            player,
            new CardSelectorPrefs(CardSelectorPrefs.DiscardSelectionPrompt, count),
            null,
            source);
        await CardCmd.Discard(choiceContext, selected);
    }
}
