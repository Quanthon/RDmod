using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class DaringDoTreasurePower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/DaringDoTreasurePower.png",
        BigIconPath: "res://RDMod/images/powers/DaringDoTreasurePower.png");
    private sealed class Data { public decimal GoldPercent; }
    protected override object InitInternalData() => new Data();
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("GoldPercent", 0m)];
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public void AddGoldPercent(decimal amount)
    {
        AssertMutable();
        GetInternalData<Data>().GoldPercent += amount;
        DynamicVars["GoldPercent"].BaseValue = GetInternalData<Data>().GoldPercent;
    }
    public override Task AfterCombatEnd(CombatRoom room)
    {
        DaringDoRewards.SetGoldBonus(room, Owner.Player!, GetInternalData<Data>().GoldPercent);
        if (room.RoomType is RoomType.Elite or RoomType.Boss)
            for (int i = 0; i < Amount; i++)
                room.AddExtraReward(Owner.Player!, new RelicReward(Owner.Player!));
        return Task.CompletedTask;
    }
}
