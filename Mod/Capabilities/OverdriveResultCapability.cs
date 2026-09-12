using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using RDmod.Cards;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Models.Capabilities;

namespace RDmod.Capabilities;

public interface IOverdrivePlayedHandler
{
    Task OnOverdrivePlayed(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay,
        int energyShortfall);
}

[RegisterModelCapability]
public sealed class OverdriveResultCapability : CardPlayCapability
{
    private int _pendingEnergyShortfall;
    private int _pendingPreparationReward;
    private int _pendingFlightReward;

    public void ReserveOverdrive(int energyShortfall)
    {
        if (energyShortfall <= 0)
            return;

        OverdriveRewardPower? rewardPower = Owner?.Owner.Creature
            .GetPower<OverdriveRewardPower>();
        int preparationReward = rewardPower?.Amount ?? 0;
        int flightReward = rewardPower?.FlightReward ?? 0;
        Modify(_ =>
        {
            _pendingEnergyShortfall = energyShortfall;
            _pendingPreparationReward = preparationReward;
            _pendingFlightReward = flightReward;
        });
    }

    protected override async Task OnOwnerCardPlayed(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        if (_pendingEnergyShortfall <= 0)
            return;

        int energyShortfall = _pendingEnergyShortfall;
        int preparationReward = _pendingPreparationReward;
        int flightReward = _pendingFlightReward;

        var card = Owner ??
            throw new InvalidOperationException("Overdrive result capability has no owner.");

        if (cardPlay.IsLastInSeries)
        {
            Modify(_ =>
            {
                _pendingEnergyShortfall = 0;
                _pendingPreparationReward = 0;
                _pendingFlightReward = 0;
            });

            await CardPileCmd.AddToCombatAndPreview<OutOfControl>(
                card.Owner.Creature,
                PileType.Hand,
                energyShortfall,
                card.Owner
            );
        }

        if (card is IOverdrivePlayedHandler handler)
            await handler.OnOverdrivePlayed(choiceContext, cardPlay, energyShortfall);

        if (preparationReward <= 0 && flightReward <= 0)
            return;

        if (preparationReward > 0)
        {
            await PowerCmd.Apply<PreparationPower>(
                choiceContext,
                card.Owner.Creature,
                preparationReward,
                card.Owner.Creature,
                card
            );
        }
        if (flightReward > 0)
        {
            await PowerCmd.Apply<FlightPower>(
                choiceContext,
                card.Owner.Creature,
                flightReward,
                card.Owner.Creature,
                card
            );
        }
    }
}
