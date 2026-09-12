using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;

namespace RDmod.Mechanics;

public static class DaringDoRewards
{
    private sealed class RoomData { public Dictionary<Player, decimal> GoldPercent { get; } = []; }
    private sealed class RewardData(GoldReward original, decimal percent)
    {
        public GoldReward Original { get; } = original;
        public decimal Percent { get; } = percent;
        public bool Applied;
    }
    private static readonly ConditionalWeakTable<CombatRoom, RoomData> Rooms = new();
    private static readonly ConditionalWeakTable<RewardsSet, RewardData> Sets = new();

    public static void SetGoldBonus(CombatRoom room, Player player, decimal percent) =>
        Rooms.GetOrCreateValue(room).GoldPercent[player] = percent;

    public static void CaptureBaseGold(RewardsSet rewards)
    {
        if (rewards.Room is not CombatRoom room || !Rooms.TryGetValue(room, out RoomData? data) ||
            !data.GoldPercent.TryGetValue(rewards.Player, out decimal percent)) return;
        // Native room gold precedes ExtraRewards. Never multiply separately awarded gold.
        GoldReward? original = rewards.Rewards.OfType<GoldReward>().FirstOrDefault(reward =>
            !room.ExtraRewards.TryGetValue(rewards.Player, out List<Reward>? extras) || !extras.Contains(reward));
        if (original != null && !Sets.TryGetValue(rewards, out _))
            Sets.Add(rewards, new RewardData(original, percent));
    }

    public static async Task AddGoldAfterGeneration(Task generation, RewardsSet rewards)
    {
        await generation;
        if (!Sets.TryGetValue(rewards, out RewardData? data) || data.Applied) return;
        data.Applied = true;
        int bonus = (int)Math.Floor(data.Original.Amount * data.Percent / 100m);
        if (bonus > 0) rewards.Rewards.Add(new GoldReward(bonus, rewards.Player));
    }
}
