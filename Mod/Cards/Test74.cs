using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test74 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int PreparationPerTrigger = 1;
    private const int MaxRepeatCount = 100;

    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[1], upgrade[1]
        new CardsVar(2),
        // RDDesign: base[2], upgrade[2]
        new BlockVar(2m, ValueProp.Move),
        ModCardVars.Computed(
            "CalculatedRepeats",
            0,
            CalculateRepeatCount)
    ];

    public override bool GainsBlock => true;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation];

    private static decimal CalculateRepeatCount(CardModel? card)
    {
        if (card?.Owner.PlayerCombatState is null)
            return 0;

        int preparation = Math.Max(
            card.Owner.Creature.GetPower<PreparationPower>()?.Amount ?? 0,
            0);
        int repeats = Math.Min(
            preparation / PreparationPerTrigger,
            MaxRepeatCount);
        int openHandSlots = Math.Max(
            CardPile.MaxCardsInHand
                - PileType.Hand.GetPile(card.Owner).Cards.Count
                + (card.Pile?.Type == PileType.Hand ? 1 : 0),
            0);
        if (repeats == 0 || openHandSlots == 0)
            return 0;

        int drawableCards = PileType.Draw.GetPile(card.Owner).Cards.Count
            + PileType.Discard.GetPile(card.Owner).Cards.Count;
        if (drawableCards < openHandSlots)
            return repeats;

        int cardsPerRepeat = Math.Max(card.DynamicVars.Cards.IntValue, 1);
        int repeatsUntilFull =
            (openHandSlots + cardsPerRepeat - 1) / cardsPerRepeat;
        return Math.Min(repeats, repeatsUntilFull);
    }

    public Test74() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        for (int repeat = 0;
             repeat < MaxRepeatCount
                 && PileType.Hand.GetPile(Owner).Cards.Count < CardPile.MaxCardsInHand;
             repeat++)
        {
            PreparationPower? preparation = Owner.Creature.GetPower<PreparationPower>();
            if (preparation is null || preparation.Amount < PreparationPerTrigger)
                break;

            await PowerCmd.ModifyAmount(
                choiceContext,
                preparation,
                -PreparationPerTrigger,
                Owner.Creature,
                this);
            await CardPileCmd.Draw(choiceContext, DynamicVars.Cards.BaseValue, Owner);
            await CreatureCmd.GainBlock(Owner.Creature, DynamicVars.Block, cardPlay);
        }
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Block.UpgradeValueBy(2m);
    }
}