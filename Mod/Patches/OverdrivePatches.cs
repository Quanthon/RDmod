using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Runs;
using RDmod.Mechanics;
using RDmod.Visuals;
using STS2RitsuLib.Patching.Core;
using STS2RitsuLib.Patching.Models;

namespace RDmod.Patches;

public sealed class OverdrivePatchSet : IModPatches
{
    public static void AddTo(ModPatcher patcher)
    {
        patcher.RegisterPatch<OverdriveResourceCheckPatch>();
        patcher.RegisterPatch<OverdriveSpendResourcesPatch>();
        patcher.RegisterPatch<OverdriveCostGlowPatch>();
    }
}

public sealed class OverdriveCostGlowPatch : IPatchMethod
{
    public static string PatchId => "rdmod_overdrive_cost_glow";
    public static string Description => "Show a red pulse behind the energy icon when a card would use Overdrive.";
    public static bool IsCritical => false;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(typeof(NCard), nameof(NCard.UpdateVisuals))
    ];

    public static void Postfix(
        NCard __instance,
        PileType pileType,
        CardPreviewMode previewMode)
    {
        OverdriveCostGlow.Update(__instance, pileType, previewMode);
    }
}

public sealed class OverdriveResourceCheckPatch : IPatchMethod
{
    public static string PatchId => "rdmod_overdrive_resource_check";
    public static string Description => "Allow manual energy overdraw while Overdrive has remaining uses.";
    public static bool IsCritical => true;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(typeof(PlayerCombatState), nameof(PlayerCombatState.HasEnoughResourcesFor))
    ];

    public static void Postfix(
        CardModel card,
        ref UnplayableReason reason,
        ref bool __result)
    {
        if (!reason.HasFlag(UnplayableReason.EnergyCostTooHigh) ||
            !OverdriveRules.CanOverdrive(card))
        {
            return;
        }

        reason &= ~UnplayableReason.EnergyCostTooHigh;
        __result = reason == UnplayableReason.None;
    }
}

public sealed class OverdriveSpendResourcesPatch : IPatchMethod
{
    public static string PatchId => "rdmod_overdrive_spend_resources";
    public static string Description => "Record manual energy overdraw and reserve its OutOfControl penalty.";
    public static bool IsCritical => true;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(typeof(CardModel), nameof(CardModel.SpendResources))
    ];

    public static void Prefix(CardModel __instance)
    {
        if (RunManager.Instance.ActionExecutor.CurrentlyRunningAction is not PlayCardAction)
            return;

        int shortfall = OverdriveRules.GetEnergyShortfall(__instance);
        if (shortfall > 0 && OverdriveRules.CanOverdrive(__instance))
            OverdriveRules.ReserveOverdraft(__instance, shortfall);
    }
}
