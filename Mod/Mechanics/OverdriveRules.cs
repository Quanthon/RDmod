using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using RDmod.Capabilities;
using RDmod.Cards;
using RDmod.Powers;
using STS2RitsuLib.Models.Capabilities;

namespace RDmod.Mechanics;

public static class OverdriveRules
{
    public static IEnumerable<IHoverTip> GetKeywordHoverTips(AbstractModel source)
    {
        return
        [
            KeywordHoverTips.Overdrive(source),
            HoverTipFactory.FromCard<OutOfControl>()
        ];
    }

    public static OverdrivePower? GetAvailablePower(CardModel card)
    {
        if (!HasValidOverdrivePaymentContext(card))
            return null;

        OverdrivePower? power = card.Owner.Creature.GetPower<OverdrivePower>();
        return power is { RemainingUses: > 0 } ? power : null;
    }

    public static LowHandOverdrivePower? GetAvailableLowHandPower(CardModel card)
    {
        if (!HasValidOverdrivePaymentContext(card))
            return null;

        LowHandOverdrivePower? power =
            card.Owner.Creature.GetPower<LowHandOverdrivePower>();
        return power is not null && power.CanOverdrive(card) ? power : null;
    }

    public static bool CanOverdrive(CardModel card)
    {
        if (!HasValidOverdrivePaymentContext(card))
            return false;

        return card.Capability<IntrinsicOverdriveCapability>() is not null ||
               card.Capability<TemporaryCardOverdriveCapability>() is not null ||
               GetAvailableLowHandPower(card) is not null ||
               card.Owner.Creature.GetPower<OverdrivePower>() is { RemainingUses: > 0 };
    }

    public static void ReserveOverdraft(CardModel card, int energyShortfall)
    {
        if (energyShortfall <= 0)
            return;

        IntrinsicOverdriveCapability? intrinsic =
            card.Capability<IntrinsicOverdriveCapability>();
        if (intrinsic is not null)
        {
            ReserveResult(card, energyShortfall);
            return;
        }

        TemporaryCardOverdriveCapability? temporaryCard =
            card.Capability<TemporaryCardOverdriveCapability>();
        if (temporaryCard is not null)
        {
            ReserveResult(card, energyShortfall);
            return;
        }

        LowHandOverdrivePower? lowHandPower = GetAvailableLowHandPower(card);
        if (lowHandPower is not null)
        {
            ReserveResult(card, energyShortfall);
            return;
        }

        OverdrivePower? power = GetAvailablePower(card);
        if (power is null)
            return;

        ReserveResult(card, energyShortfall);
        power.ReserveUse(card);
    }

    private static void ReserveResult(CardModel card, int energyShortfall)
    {
        card.GetOrCreateCapability<OverdriveResultCapability>()
            .ReserveOverdrive(energyShortfall);
    }

    public static int GetEnergyShortfall(CardModel card)
    {
        if (card.Owner?.PlayerCombatState is not { } playerState)
            return 0;

        int cost = Math.Max(0, card.EnergyCost.GetAmountToSpend());
        return Math.Max(0, cost - playerState.Energy);
    }

    private static bool HasValidOverdrivePaymentContext(CardModel card)
    {
        if (card.Owner?.PlayerCombatState is not { } playerState ||
            card.CombatState is null ||
            card.EnergyCost.CostsX)
        {
            return false;
        }

        int cost = Math.Max(0, card.EnergyCost.GetAmountToSpend());
        if (cost <= playerState.Energy)
            return false;

        GameAction? currentAction = RunManager.Instance.ActionExecutor.CurrentlyRunningAction;
        if (currentAction is not null && currentAction is not PlayCardAction)
            return false;

        return !Hook.ShouldPayExcessEnergyCostWithStars(card.CombatState, card.Owner);
    }

    public static bool ShouldShowCostGlow(CardModel card)
    {
        if (card.Owner?.PlayerCombatState is not { Phase: PlayerTurnPhase.Play } ||
            GetEnergyShortfall(card) <= 0 ||
            !CanOverdrive(card))
        {
            return false;
        }

        return card.CanPlay();
    }
}
