using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
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
public sealed class Test28 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    public override IEnumerable<CardKeyword> CanonicalKeywords =>
        [CardKeyword.Exhaust];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    public Test28() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        CardModel? selected = (await CardSelectCmd.FromCombatPile(
            choiceContext,
            PileType.Discard.GetPile(Owner),
            Owner,
            new CardSelectorPrefs(SelectionScreenPrompt, 1)
        )).FirstOrDefault();

        if (selected is null)
            return;

        await CardPileCmd.Add(selected, PileType.Hand);
        if (selected.Pile?.Type == PileType.Hand)
            selected.GetOrCreateCapability<TemporaryCardOverdriveCapability>();
    }

    protected override void OnUpgrade()
    {
        RemoveKeyword(CardKeyword.Exhaust);
    }
}
