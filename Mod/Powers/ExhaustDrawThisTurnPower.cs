using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class ExhaustDrawThisTurnPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/ExhaustDrawThisTurnPower.png",
        BigIconPath: "res://RDMod/images/powers/ExhaustDrawThisTurnPower.png");
    private sealed class Data
    {
        public int EtherealCount;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override object InitInternalData() => new Data();
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromKeyword(CardKeyword.Exhaust)];

    public override async Task AfterCardExhausted(
        PlayerChoiceContext choiceContext,
        CardModel card,
        bool causedByEthereal)
    {
        if (card.Owner.Creature != Owner)
            return;
        if (causedByEthereal)
            GetInternalData<Data>().EtherealCount++;
        else
            await CardPileCmd.Draw(choiceContext, Amount, Owner.Player!);
    }

    public override async Task AfterSideTurnEnd(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (!participants.Contains(Owner))
            return;
        Data data = GetInternalData<Data>();
        if (data.EtherealCount > 0)
            await CardPileCmd.Draw(choiceContext, Amount * data.EtherealCount, Owner.Player!);
        await PowerCmd.Remove(this);
    }
}

