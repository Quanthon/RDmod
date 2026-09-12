using STS2RitsuLib.Scaffolding.Content;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Cards;
using STS2RitsuLib.Combat.Powers;
using STS2RitsuLib.Interop.AutoRegistration;

namespace RDmod.Powers;

[RegisterPower]
public sealed class AppleCiderStrengthPower :
    ModTemporaryAppliedPowerTemplate<AppleCider, StrengthPower>
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/AppleCiderStrengthPower.png",
        BigIconPath: "res://RDMod/images/powers/AppleCiderStrengthPower.png");
}
