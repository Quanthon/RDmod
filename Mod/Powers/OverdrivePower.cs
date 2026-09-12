using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class OverdrivePower : ModPowerTemplate
{
    private sealed class Data
    {
        public int ReservedUses;
        public HashSet<CardModel> PendingCards { get; } = [];
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/OverdrivePower.png",
        BigIconPath: "res://RDMod/images/powers/OverdrivePower.png"
    );

    public int RemainingUses => IsMutable
        ? Math.Max(0, Amount - GetInternalData<Data>().ReservedUses)
        : Amount;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    protected override object InitInternalData() => new Data();

    public bool CanOverdrive(CardModel card)
    {
        return card.Owner.Creature == Owner && RemainingUses > 0;
    }

    public void ReserveUse(CardModel card)
    {
        if (!CanOverdrive(card))
            return;

        Data data = GetInternalData<Data>();
        data.ReservedUses++;
        data.PendingCards.Add(card);
    }

    public override async Task AfterCardPlayed(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        if (cardPlay.Card.Owner.Creature != Owner ||
            cardPlay.PlayIndex != cardPlay.PlayCount - 1)
        {
            return;
        }

        Data data = GetInternalData<Data>();
        if (!data.PendingCards.Remove(cardPlay.Card))
            return;

        data.ReservedUses--;
        await PowerCmd.Decrement(this);
    }

    public override async Task AfterSideTurnEnd(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner))
            await PowerCmd.Remove(this);
    }
}
