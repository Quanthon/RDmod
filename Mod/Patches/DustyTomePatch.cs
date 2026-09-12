using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models.Relics;
using RDmod.Characters;
using STS2RitsuLib.Patching.Models;

namespace RDmod.Patches;

public sealed class RainbowDashDustyTomePatch : IPatchMethod
{
    public static string PatchId => "rdmod_dusty_tome_empty_pool_fallback";
    public static string Description => "Use RD ancient cards when Dusty Tome's tooth exclusion leaves no candidates.";
    public static bool IsCritical => true;

    public static ModPatchTarget[] GetTargets() =>
    [
        new(typeof(DustyTome), nameof(DustyTome.SetupForPlayer))
    ];

    public static bool Prefix(DustyTome __instance, Player player)
    {
        if (player.Character is not RainbowDashCharacter)
            return true;

        var ancientCards = player.Character.CardPool
            .GetUnlockedCards(player.UnlockState, player.RunState.CardMultiplayerConstraint)
            .Where(card => card.Rarity == CardRarity.Ancient).ToList();
        if (ancientCards.Count == 0 ||
            ancientCards.Any(card => !ArchaicTooth.TranscendenceCards.Contains(card)))
            return true;

        __instance.AncientCard = player.PlayerRng.Rewards.NextItem(ancientCards)!.Id;
        return false;
    }
}
