using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class PreparationPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/PreparationPower.png",
        BigIconPath: "res://RDMod/images/powers/PreparationPower.png");
    private sealed class Data
    {
        public HashSet<CardModel> BoostedCards { get; } = [];
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new DynamicVar("DamageIncrease", 50m)
    ];

    protected override object InitInternalData() => new Data();

    public override Task BeforeCardPlayed(CardPlay cardPlay)
    {
        if (cardPlay.PlayIndex == 0 &&
            cardPlay.Card.Owner.Creature == Owner &&
            cardPlay.Card.Type == CardType.Attack &&
            cardPlay.Card is not IPreservesPreparationOnPlay &&
            Owner.GetPower<PreparationPreservationPower>() is null &&
            Owner.GetPower<Test68Power>() is null &&
            Amount > 0)
        {
            GetInternalData<Data>().BoostedCards.Add(cardPlay.Card);
        }

        return Task.CompletedTask;
    }

    public override decimal ModifyDamageMultiplicative(
        Creature? target,
        decimal amount,
        ValueProp props,
        Creature? dealer,
        CardModel? cardSource,
        CardPlay? cardPlay)
    {
        if (dealer != Owner ||
            cardSource is null ||
            cardSource.Owner.Creature != Owner ||
            cardSource.Type != CardType.Attack ||
            !props.IsPoweredAttack() ||
            (Amount <= 0 && !GetInternalData<Data>().BoostedCards.Contains(cardSource)))
        {
            return 1m;
        }

        return 1m + DynamicVars["DamageIncrease"].BaseValue / 100m;
    }

    public override async Task AfterCardPlayed(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        if (cardPlay.PlayIndex != cardPlay.PlayCount - 1 ||
            !GetInternalData<Data>().BoostedCards.Remove(cardPlay.Card))
        {
            return;
        }

        await PowerCmd.Decrement(this);
    }
}

