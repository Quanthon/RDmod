using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class CardSelfDamageNextTurnDrawPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/CardSelfDamageNextTurnDrawPower.png",
        BigIconPath: "res://RDMod/images/powers/CardSelfDamageNextTurnDrawPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override async Task AfterDamageReceived(
        PlayerChoiceContext choiceContext,
        Creature target,
        DamageResult result,
        ValueProp props,
        Creature? dealer,
        CardModel? cardSource)
    {
        if (target != Owner ||
            result.TotalDamage <= 0 ||
            cardSource is null ||
            cardSource.Owner.Creature != Owner)
        {
            return;
        }

        Flash();
        foreach (CardModel card in await CardPileCmd.Draw(choiceContext, Amount, Owner.Player!))
        {
            CardCmd.ApplySingleTurnRetain(card);
        }
    }
}
