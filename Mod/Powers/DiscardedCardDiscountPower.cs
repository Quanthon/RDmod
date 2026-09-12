using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class DiscardedCardDiscountPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/DiscardedCardDiscountPower.png",
        BigIconPath: "res://RDMod/images/powers/DiscardedCardDiscountPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override Task AfterCardDiscarded(
        PlayerChoiceContext choiceContext,
        CardModel card)
    {
        if (card.Owner.Creature == Owner)
        {
            Flash();
            card.EnergyCost.AddThisCombat(-Amount, reduceOnly: true);
        }

        return Task.CompletedTask;
    }
}
