using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class DaringDoConPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/DaringDoConPower.png",
        BigIconPath: "res://RDMod/images/powers/DaringDoConPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override Task AfterCombatEnd(CombatRoom room)
    {
        for (int i = 0; i < Amount; i++)
            room.AddExtraReward(Owner.Player!, new CardReward(CardCreationOptions.ForRoom(Owner.Player!, room.RoomType), 3, Owner.Player!));
        return Task.CompletedTask;
    }
}
