using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Extensions;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using RDmod.Cards;

namespace RDmod.Mechanics;

public static class DaringDoCards
{
    public static IEnumerable<CardModel> Pool =>
    [
        ModelDb.Card<DaringDoBindUp>(), ModelDb.Card<DaringDoCon>(), ModelDb.Card<DaringDoDodge>(),
        ModelDb.Card<DaringDoPuzzle>(), ModelDb.Card<DaringDoRob>(), ModelDb.Card<DaringDoStrike>(),
        ModelDb.Card<DaringDoTreasure>()
    ];
    public static IEnumerable<IHoverTip> HoverTips =>
    [
        HoverTipFactory.FromCard<DaringDoBindUp>(), HoverTipFactory.FromCard<DaringDoCon>(),
        HoverTipFactory.FromCard<DaringDoDodge>(), HoverTipFactory.FromCard<DaringDoPuzzle>(),
        HoverTipFactory.FromCard<DaringDoRob>(), HoverTipFactory.FromCard<DaringDoStrike>(),
        HoverTipFactory.FromCard<DaringDoTreasure>()
    ];
    // Explicit Daring Do effects may generate these cards despite their random-generation exclusion.
    public static IEnumerable<CardModel> CreateChoices(Player owner, int count) =>
        Pool.TakeRandom(count, owner.RunState.Rng.CombatCardGeneration)
            .Select(card => owner.Creature.CombatState!.CreateCard(card, owner));

    public static async Task AddRandomToHand(Player owner)
    {
        CardModel card = CreateChoices(owner, 1).Single();
        await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Hand, owner);
    }
}
