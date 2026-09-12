using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Entities.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class OverdriveRewardPower : ModPowerTemplate
{
    private sealed class Data
    {
        public int FlightReward;
    }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("FlightReward", 0m)];
    public override PowerType Type => PowerType.Buff;
    protected override object InitInternalData() => new Data();
    public int FlightReward => GetInternalData<Data>().FlightReward;

    public void AddFlightReward(int amount)
    {
        AssertMutable();
        GetInternalData<Data>().FlightReward += amount;
        DynamicVars["FlightReward"].BaseValue = FlightReward;
    }
    public override PowerStackType StackType => PowerStackType.Counter;

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/OverdriveRewardPower.png",
        BigIconPath: "res://RDMod/images/powers/OverdriveRewardPower.png"
    );
}
