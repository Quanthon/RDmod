using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using RDmod.Cards;

namespace RDmod.Mechanics;

public static class CardGenerationOperations
{
    public static async Task<IReadOnlyList<AppleCider>> AddAppleCidersToHand(
        CardModel source,
        int count,
        bool upgraded = false)
    {
        ICombatState combatState = source.CombatState
            ?? throw new InvalidOperationException("Apple Cider generation requires combat.");
        return await AddAppleCidersToHand(
            combatState,
            source.Owner,
            count,
            upgraded);
    }

    public static async Task<IReadOnlyList<AppleCider>> AddAppleCidersToHand(
        ICombatState combatState,
        Player owner,
        int count,
        bool upgraded = false)
    {
        if (count <= 0)
            return [];

        List<AppleCider> cards = [];
        for (int i = 0; i < count; i++)
        {
            AppleCider card = combatState.CreateCard<AppleCider>(owner);
            if (upgraded)
                CardCmd.Upgrade(card);
            cards.Add(card);
        }

        await CardPileCmd.AddGeneratedCardsToCombat(
            cards,
            PileType.Hand,
            owner);
        return cards;
    }
}
