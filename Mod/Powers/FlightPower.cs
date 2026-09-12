using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class FlightPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/FlightPower.png",
        BigIconPath: "res://RDMod/images/powers/FlightPower.png");
    private sealed class Data
    {
        public int PendingFlightLoss;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    private int PendingFlightLoss
    {
        get => GetInternalData<Data>().PendingFlightLoss;
        set
        {
            AssertMutable();
            GetInternalData<Data>().PendingFlightLoss = value;
        }
    }

    protected override object InitInternalData()
    {
        return new Data();
    }

    public override async Task AfterPowerAmountChanged(
        PlayerChoiceContext choiceContext,
        PowerModel power,
        decimal amount,
        Creature? applier,
        CardModel? cardSource)
    {
        if (power != this || Owner.IsDead)
            return;

        decimal previousAmount = power.Amount - amount;
        if (amount > 0 && previousAmount <= 0)
        {
            await CreatureCmd.TriggerAnim(Owner, "FlightOn", 0f);
        }
        else if (amount < 0 && power.Amount <= 0)
        {
            await CreatureCmd.TriggerAnim(Owner, "FlightOff", 0f);
        }
    }

    public override decimal ModifyDamageAdditive(
        Creature? target,
        decimal amount,
        ValueProp props,
        Creature? dealer,
        CardModel? cardSource,
        CardPlay? cardPlay)
    {
        if (target != Owner ||
            dealer is null ||
            dealer.Side == Owner.Side ||
            !props.IsPoweredAttack())
        {
            return 0m;
        }

        return -Math.Max(Amount, 0);
    }

    public override Task AfterAttack(PlayerChoiceContext choiceContext, AttackCommand command)
    {
        if (command.Attacker is null ||
            command.Attacker.Side == Owner.Side ||
            !command.DamageProps.IsPoweredAttack())
        {
            return Task.CompletedTask;
        }

        int hitCount = command.Results
            .SelectMany(results => results)
            .Count(result => result.Receiver == Owner);

        if (hitCount > 0)
            PendingFlightLoss += hitCount;

        return Task.CompletedTask;
    }

    public override async Task BeforeSideTurnStart(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IReadOnlyList<Creature> participants,
        ICombatState combatState)
    {
        if (!participants.Contains(Owner) || PendingFlightLoss <= 0)
            return;

        int flightLoss = PendingFlightLoss;
        PendingFlightLoss = 0;
        FlightPreservationPower? preservation =
            Owner.GetPower<FlightPreservationPower>();
        if (preservation is not null)
        {
            preservation.NotifyPreventedFlightLoss();
            return;
        }

        await PowerCmd.ModifyAmount(choiceContext, this, -flightLoss, null, null);
    }
}
