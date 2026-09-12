using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class DaisyPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/DaisyPower.png",
        BigIconPath: "res://RDMod/images/powers/DaisyPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    public override async Task AfterCardDiscarded(
        PlayerChoiceContext choiceContext,
        CardModel card)
    {
        if (card.Owner.Creature != Owner || Owner.Side != CombatState.CurrentSide)
            return;

        Flash();
        await CardPileCmd.Draw(choiceContext, 1m, Owner.Player!);
    }
}
