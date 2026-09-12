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

public abstract class TypedHandRetainPower : ModPowerTemplate
{
    protected abstract CardType RetainedType { get; }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        RetainMatchingCards();
        return Task.CompletedTask;
    }

    public override Task AfterCardChangedPiles(
        CardModel card,
        PileType oldPileType,
        AbstractModel? clonedBy)
    {
        if (card.Owner.Creature == Owner &&
            card.Pile?.Type == PileType.Hand &&
            card.Type == RetainedType)
        {
            card.GiveSingleTurnRetain();
        }
        return Task.CompletedTask;
    }

    public override async Task AfterSideTurnEnd(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (!participants.Contains(Owner))
            return;

        RetainMatchingCards();
        await PowerCmd.Remove(this);
    }

    private void RetainMatchingCards()
    {
        if (Owner.Player is not { } player)
            return;

        foreach (CardModel card in PileType.Hand.GetPile(player).Cards)
        {
            if (card.Type == RetainedType)
                card.GiveSingleTurnRetain();
        }
    }
}

[RegisterPower]
public sealed class RetainSkillsThisTurnPower : TypedHandRetainPower
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/RetainSkillsThisTurnPower.png",
        BigIconPath: "res://RDMod/images/powers/RetainSkillsThisTurnPower.png");
    protected override CardType RetainedType => CardType.Skill;
}

[RegisterPower]
public sealed class RetainAttacksThisTurnPower : TypedHandRetainPower
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/RetainAttacksThisTurnPower.png",
        BigIconPath: "res://RDMod/images/powers/RetainAttacksThisTurnPower.png");
    protected override CardType RetainedType => CardType.Attack;
}
