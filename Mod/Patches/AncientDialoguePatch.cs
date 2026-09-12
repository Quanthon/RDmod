using MegaCrit.Sts2.Core.Entities.Ancients;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using STS2RitsuLib.Patching.Models;

namespace RDmod.Patches;

public sealed class RainbowDashAncientDialoguePatch : IPatchMethod
{
    public static string PatchId => "rdmod_prefer_character_ancient_dialogue";
    public static string Description => "Prefer eligible Rainbow Dash ancient dialogue over generic dialogue.";
    public static bool IsCritical => true;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(typeof(AncientDialogueSet), nameof(AncientDialogueSet.GetValidDialogues))
    ];

    public static void Prefix(
        AncientDialogueSet __instance,
        ModelId characterId,
        int charVisits,
        ref bool allowAnyCharacterDialogues)
    {
        if (characterId != ModelDb.GetId<RainbowDashCharacter>() ||
            !__instance.CharacterDialogues.TryGetValue(characterId.Entry, out var dialogues))
            return;

        // Preserve the original first-ever introduction and fallback when no RD line is eligible.
        if (dialogues.Any(dialogue => dialogue.VisitIndex == charVisits ||
            (dialogue.IsRepeating && (!dialogue.VisitIndex.HasValue || dialogue.VisitIndex <= charVisits))))
            allowAnyCharacterDialogues = false;
    }
#if DEBUG
    public static void Postfix(ModelId characterId, IEnumerable<AncientDialogue> __result)
    {
        if (characterId != ModelDb.GetId<RainbowDashCharacter>())
            return;
        var lines = __result.SelectMany(dialogue => dialogue.Lines)
            .Select(line => line.LineText.LocEntryKey).ToArray();
        RDmod.Scripts.Entry.Logger.Info("RD_ANCIENT_DIALOGUE_POOL " + string.Join("|", lines));
    }
#endif

}
