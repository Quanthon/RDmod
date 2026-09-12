using MegaCrit.Sts2.Core.ValueProps;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test84 : ModCardTemplate
{
    public override bool GainsBlock => true;

    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new BlockVar(1m, ValueProp.Move),
        // RDDesign: base[1], upgrade[1]
        new PowerVar<FlightPower>(1m),
        // RDDesign: base[2], upgrade[2]
        new CardsVar("ExhaustCards", 1)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
    [
        RDmod.Mechanics.KeywordHoverTips.Flight,
        HoverTipFactory.FromKeyword(CardKeyword.Exhaust)
    ];

    public Test84() : base(
        0,
        CardType.Skill,
        CardRarity.Common,
        TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        await CreatureCmd.GainBlock(Owner.Creature, DynamicVars.Block, cardPlay);

        await PowerCmd.Apply<FlightPower>(
            choiceContext,
            Owner.Creature,
            DynamicVars["FlightPower"].BaseValue,
            Owner.Creature,
            this);

        IReadOnlyList<CardModel> hand = PileType.Hand.GetPile(Owner).Cards;
        if (hand.Count == 0)
            return;

        CardModel? card;
        if (IsUpgraded)
        {
            card = (await CardSelectCmd.FromHand(
                choiceContext,
                Owner,
                new CardSelectorPrefs(
                    SelectionScreenPrompt,
                    DynamicVars["ExhaustCards"].IntValue),
                null,
                this)).FirstOrDefault();
        }
        else
        {
            card = Owner.RunState.Rng.CombatCardSelection.NextItem(hand);
        }

        if (card is not null)
            await CardCmd.Exhaust(choiceContext, card);
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Block.UpgradeValueBy(1m);
        // Upgrade also changes random selection into player choice.
    }
}
