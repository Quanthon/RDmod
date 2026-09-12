using MegaCrit.Sts2.Core.Rewards;
using RDmod.Mechanics;
using STS2RitsuLib.Patching.Core;
using STS2RitsuLib.Patching.Models;

namespace RDmod.Patches;

public sealed class DaringDoRewardPatchSet : IModPatches
{
    public static void AddTo(ModPatcher patcher)
    {
        patcher.RegisterPatch<DaringDoBaseGoldPatch>();
        patcher.RegisterPatch<DaringDoGoldGeneratedPatch>();
    }
}

public sealed class DaringDoBaseGoldPatch : IPatchMethod
{
    public static string PatchId => "rdmod_daring_do_base_gold";
    public static string Description => "Remember native combat gold before other reward hooks.";
    public static bool IsCritical => true;
    public static ModPatchTarget[] GetTargets() => [new(typeof(RewardsSet), nameof(RewardsSet.WithRewardsFromRoom))];
    public static void Postfix(RewardsSet __instance) => DaringDoRewards.CaptureBaseGold(__instance);
}

public sealed class DaringDoGoldGeneratedPatch : IPatchMethod
{
    public static string PatchId => "rdmod_daring_do_gold_generated";
    public static string Description => "Add the additive Daring Do bonus after native gold has been rolled.";
    public static bool IsCritical => true;
    public static ModPatchTarget[] GetTargets() => [new(typeof(RewardsSet), nameof(RewardsSet.GenerateWithoutOffering))];
    public static void Postfix(RewardsSet __instance, ref Task __result) =>
        __result = DaringDoRewards.AddGoldAfterGeneration(__result, __instance);
}
