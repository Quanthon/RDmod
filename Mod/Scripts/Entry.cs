using System.Reflection;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;
using STS2RitsuLib;
using STS2RitsuLib.Interop;
using STS2RitsuLib.Patching.Core;
using RDmod.Capabilities;
using RDmod.Cards;
using RDmod.Patches;
using TakeOffRelic = RDmod.Relics.TakeOff;
using UnstoppableRelic = RDmod.Relics.Unstoppable;

namespace RDmod.Scripts;

[ModInitializer(nameof(Init))]
public static class Entry
{
    public const string ModId = "RDMod";

    public static Logger Logger { get; private set; } = null!;

    public static void Init()
    {
        Assembly assembly = Assembly.GetExecutingAssembly();

        Logger = RitsuLibFramework.CreateLogger(ModId);
        ModTypeDiscoveryHub.RegisterModAssembly(ModId, assembly);
        RitsuLibFramework.RegisterTouchOfOrobasRefinementMapping<
            TakeOffRelic,
            UnstoppableRelic>();
        RitsuLibFramework.RegisterArchaicToothTranscendenceMapping<
            Charge,
            UltraCharge>();

        RitsuLibFramework.GetContentRegistry(ModId)
            .ConfigureDefaultModelCapabilities<Test3>(
                CardCapabilityModifierId<Test3>("intrinsic-overdrive"),
                (_, capabilities) => capabilities.Add<IntrinsicOverdriveCapability>()
            );

        RitsuLibFramework.GetContentRegistry(ModId)
            .ConfigureDefaultModelCapabilities<Test12>(
                CardCapabilityModifierId<Test12>("overdrive-result"),
                (_, capabilities) => capabilities.Add<OverdriveResultCapability>()
            );

        RitsuLibFramework.GetContentRegistry(ModId)
            .ConfigureDefaultModelCapabilities<Test20>(
                CardCapabilityModifierId<Test20>("overdrive-result"),
                (_, capabilities) => capabilities.Add<OverdriveResultCapability>()
            );

        // 你的项目包含 PCK 和挂载在场景上的 C# 脚本，因此保留这一步。
        RitsuLibFramework.EnsureGodotScriptsRegistered(assembly, Logger);

        var patcher = RitsuLibFramework.CreatePatcher(ModId, "mechanics");
        patcher.RegisterPatches<OverdrivePatchSet>();
        patcher.RegisterPatches<CardPlayabilityPatchSet>();
        patcher.RegisterPatches<DaringDoRewardPatchSet>();
        patcher.RegisterPatch<RainbowDashAncientDialoguePatch>();
        patcher.RegisterPatch<RainbowDashDustyTomePatch>();
        if (!patcher.PatchAll())
            throw new InvalidOperationException("Critical RDMod mechanic patches failed.");

        Logger.Info("Rainbow Dash Mod initialized.");
    }

    private static string CardCapabilityModifierId<TCard>(string purpose)
    {
        return $"{typeof(TCard).Name}-{purpose}".ToLowerInvariant();
    }
}
