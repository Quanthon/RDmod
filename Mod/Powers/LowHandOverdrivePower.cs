using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class LowHandOverdrivePower : ModPowerTemplate
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/LowHandOverdrivePower.png",
        BigIconPath: "res://RDMod/images/powers/LowHandOverdrivePower.png"
    );
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    public bool CanOverdrive(CardModel card) =>
        card.Owner.Creature == Owner &&
        card.Type != CardType.Status &&
        PileType.Hand.GetPile(card.Owner).Cards.Count <= Amount;
}
