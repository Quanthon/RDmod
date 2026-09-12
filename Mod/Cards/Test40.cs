using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Factories;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using RDmod.Capabilities;
using RDmod.Characters;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Models.Capabilities;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test40 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int ChoiceCount = 4;

    // RDDesign: base[1], upgrade[1], localization[1]
    private const int SelectionCount = 1;

    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => OverdriveRules.GetKeywordHoverTips(this);

    public Test40() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        IEnumerable<CardModel> candidates = Owner.UnlockState.CharacterCardPools
            .SelectMany(pool => pool.GetUnlockedCards(
                Owner.UnlockState, Owner.RunState.CardMultiplayerConstraint))
            .Where(card => card.Rarity is CardRarity.Common or CardRarity.Uncommon or CardRarity.Rare);
        List<CardModel> choices = CardFactory.GetDistinctForCombat(
            Owner, candidates, ChoiceCount, Owner.RunState.Rng.CombatCardGeneration).ToList();

        if (IsUpgraded)
        {
            foreach (CardModel choice in choices)
                CardCmd.Upgrade(choice);
        }

        IEnumerable<CardModel> selected = await CardSelectCmd.FromSimpleGrid(
            choiceContext,
            choices,
            Owner,
            new CardSelectorPrefs(SelectionScreenPrompt, SelectionCount)
        );
        foreach (CardModel card in selected)
        {
            card.GetOrCreateCapability<TemporaryCardOverdriveCapability>();
            await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Hand, Owner);
        }
    }

    protected override void OnUpgrade() { }
}
