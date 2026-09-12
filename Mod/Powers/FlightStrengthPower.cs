using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class FlightStrengthPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/FlightStrengthPower.png",
        BigIconPath: "res://RDMod/images/powers/FlightStrengthPower.png");
    private sealed class Data
    {
        public bool Active;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
    [
        RDmod.Mechanics.KeywordHoverTips.Flight,
        HoverTipFactory.FromPower<StrengthPower>()
    ];

    protected override object InitInternalData() => new Data();

    public override async Task AfterPowerAmountChanged(
        PlayerChoiceContext choiceContext,
        PowerModel power,
        decimal amount,
        Creature? applier,
        CardModel? cardSource)
    {
        Data data = GetInternalData<Data>();
        if (power == this && amount > 0 && Owner.GetPower<FlightPower>() is not null)
        {
            decimal strengthGain = data.Active ? amount : Amount;
            AssertMutable();
            data.Active = true;
            await ApplyStrength(choiceContext, strengthGain, applier, cardSource);
            return;
        }

        if (power is not FlightPower || power.Owner != Owner)
            return;

        if (!data.Active && amount > 0 && power.Amount > 0)
        {
            AssertMutable();
            data.Active = true;
            Flash();
            await ApplyStrength(choiceContext, Amount, applier, cardSource);
        }
        else if (data.Active && amount < 0 && power.Amount <= 0)
        {
            AssertMutable();
            data.Active = false;
            Flash();
            await ApplyStrength(choiceContext, -Amount, applier, cardSource);
        }
    }

    public override async Task AfterRemoved(Creature oldOwner)
    {
        if (!GetInternalData<Data>().Active || oldOwner.CombatState is null)
            return;

        await PowerCmd.Apply<StrengthPower>(
            new ThrowingPlayerChoiceContext(),
            oldOwner,
            -Amount,
            oldOwner,
            null,
            silent: true
        );
    }

    private Task ApplyStrength(
        PlayerChoiceContext choiceContext,
        decimal amount,
        Creature? applier,
        CardModel? cardSource)
    {
        return PowerCmd.Apply<StrengthPower>(
            choiceContext,
            Owner,
            amount,
            applier,
            cardSource,
            silent: true
        );
    }
}
