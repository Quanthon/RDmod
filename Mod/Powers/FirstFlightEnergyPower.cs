using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class FirstFlightEnergyPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/FirstFlightEnergyPower.png",
        BigIconPath: "res://RDMod/images/powers/FirstFlightEnergyPower.png");
    private sealed class Data
    {
        public bool TriggeredThisTurn;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
    [
        RDmod.Mechanics.KeywordHoverTips.Flight
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
        if (data.TriggeredThisTurn ||
            amount <= 0 ||
            power is not FlightPower ||
            power.Owner != Owner ||
            Owner.Player is not { } player)
        {
            return;
        }

        AssertMutable();
        data.TriggeredThisTurn = true;
        Flash();
        await PlayerCmd.GainEnergy(Amount, player);
    }

    public override Task BeforeSideTurnStart(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IReadOnlyList<Creature> participants,
        ICombatState combatState)
    {
        if (participants.Contains(Owner))
        {
            AssertMutable();
            GetInternalData<Data>().TriggeredThisTurn = false;
        }

        return Task.CompletedTask;
    }
}
