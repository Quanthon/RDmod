using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class DaringDoFiction : ModCardTemplate
{
    // RDDesignManualUpgrade: upgrade[0] - ChoiceCount supplies the upgraded-only random choice count.
    private const int ChoiceCount = 2;
    // RDDesignManualUpgrade: upgrade[1] - SelectionCount supplies the upgraded-only selection count.
    private const int SelectionCount = 1;

    public override CardAssetProfile AssetProfile => new(PortraitPath: "res://RDMod/images/cards/DaringDoFiction.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    public DaringDoFiction() : base(0, CardType.Skill, CardRarity.Rare, TargetType.Self) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        if (!IsUpgraded)
        {
            await DaringDoCards.AddRandomToHand(Owner);
            return;
        }

        List<CardModel> choices = DaringDoCards.CreateChoices(Owner, ChoiceCount).ToList();
        IEnumerable<CardModel> selected = await CardSelectCmd.FromSimpleGrid(
            choiceContext, choices, Owner,
            new CardSelectorPrefs(SelectionScreenPrompt, SelectionCount));
        foreach (CardModel card in selected)
            await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Hand, Owner);
    }
    protected override void OnUpgrade() { }
}
