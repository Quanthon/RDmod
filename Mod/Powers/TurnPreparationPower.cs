using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class TurnPreparationPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/TurnPreparationPower.png",
        BigIconPath: "res://RDMod/images/powers/TurnPreparationPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
    [
        RDmod.Mechanics.KeywordHoverTips.Preparation
    ];

    public override async Task AfterCardExhausted(
        PlayerChoiceContext choiceContext, CardModel card, bool causedByEthereal)
    {
        if (card.Owner.Creature != Owner)
            return;
        Flash();
        await PowerCmd.Apply<PreparationPower>(choiceContext, Owner, Amount, Owner, null);
    }
}
