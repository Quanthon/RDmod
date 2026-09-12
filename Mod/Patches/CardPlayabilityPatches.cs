using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using RDmod.Cards;
using STS2RitsuLib.Patching.Core;
using STS2RitsuLib.Patching.Models;

namespace RDmod.Patches;

public sealed class CardPlayabilityPatchSet : IModPatches
{
    public static void AddTo(ModPatcher patcher)
    {
        patcher.RegisterPatch<Test53UnplayableMessagePatch>();
    }
}

public sealed class Test53UnplayableMessagePatch : IPatchMethod
{
    private static readonly Type UnplayableReasonExtensionsType =
        typeof(UnplayableReason).Assembly.GetType(
            "MegaCrit.Sts2.Core.Entities.Cards.UnplayableReasonExtensions")
        ?? throw new TypeLoadException("UnplayableReasonExtensions was not found.");

    public static string PatchId => "rdmod_test53_unplayable_message";
    public static string Description =>
        "Show Rainbow Dash's energy-total warning when Test53 cannot be played.";
    public static bool IsCritical => true;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(UnplayableReasonExtensionsType, "GetPlayerDialogueLine")
    ];

    public static void Postfix(
        UnplayableReason __0,
        AbstractModel? __1,
        ref LocString? __result)
    {
        if (__0.HasFlag(UnplayableReason.BlockedByHook) && __1 is Test53 test53)
            __result = test53.UnplayableMessage;
    }
}