using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace RDmod.Mechanics;

public static class CardTurnStatistics
{
    public static int EnergyValuePlayedThisTurn(CardModel card)
    {
        return CombatManager.Instance.History.CardPlaysFinished
            .Where(entry =>
                entry.HappenedThisTurn(card.CombatState) &&
                entry.CardPlay.Card.Owner == card.Owner)
            .Sum(entry => entry.CardPlay.Resources.EnergyValue);
    }

    public static bool IsGenerated(CardModel card) =>
        CombatManager.Instance.History.Entries
            .OfType<CardGeneratedEntry>()
            .Any(entry => ReferenceEquals(entry.Card, card));

    public static HashSet<CardModel> GeneratedCards() =>
        CombatManager.Instance.History.Entries
            .OfType<CardGeneratedEntry>()
            .Select(entry => entry.Card)
            .ToHashSet(
                (IEqualityComparer<CardModel>)ReferenceEqualityComparer.Instance);
}
