using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Extensions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.Models.RelicPools;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Relics;

[RegisterRelic(typeof(SharedRelicPool))]
public sealed class Test7 : ModRelicTemplate
{
    private ModelId? _selectedCardId;
    private bool _selectionCompleted;

    public override RelicRarity Rarity => RelicRarity.Shop;
    public override bool HasUponPickupEffect => true;
    public override bool IsUsedUp => SelectionCompleted && SelectedCardId is null;
    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Test7_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Test7_outline.png",
        BigIconPath: "res://RDMod/images/relics/Test7.png");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(7)];

    [SavedProperty]
    public ModelId? SelectedCardId
    {
        get => _selectedCardId;
        set
        {
            AssertMutable();
            _selectedCardId = value;
            RefreshStatus();
        }
    }

    [SavedProperty]
    public bool SelectionCompleted
    {
        get => _selectionCompleted;
        set
        {
            AssertMutable();
            _selectionCompleted = value;
            RefreshStatus();
        }
    }

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        SelectedCardId is not null
            ? [HoverTipFactory.FromCard(ModelDb.GetById<CardModel>(SelectedCardId))]
            : [];

    private void RefreshStatus() => Status = IsUsedUp ? RelicStatus.Disabled : RelicStatus.Normal;

    public override async Task AfterObtained()
    {
        if (SelectionCompleted)
            return;
        List<CardModel> choices = Owner.UnlockState.CharacterCardPools
            .Append(ModelDb.CardPool<ColorlessCardPool>())
            .SelectMany(pool => pool.GetUnlockedCards(Owner.UnlockState, Owner.RunState.CardMultiplayerConstraint))
            .Where(card => card.Rarity is CardRarity.Common or CardRarity.Uncommon or CardRarity.Rare)
            .Where(card => card.CanBeGeneratedInCombat)
            .Distinct()
            .TakeRandom(DynamicVars.Cards.IntValue, Owner.RunState.Rng.Niche)
            .Select(card => Owner.RunState.CreateCard(card, Owner))
            .ToList();
        CardModel? chosen = (await CardSelectCmd.FromSimpleGrid(
            new BlockingPlayerChoiceContext(), choices, Owner,
            new CardSelectorPrefs(SelectionScreenPrompt, 0, 1))).FirstOrDefault();
        SelectedCardId = chosen?.Id;
        SelectionCompleted = true;
    }

    public override async Task BeforeCombatStart()
    {
        if (SelectedCardId is null)
            return;
        Flash();
        CardModel card = Owner.Creature.CombatState!.CreateCard(ModelDb.GetById<CardModel>(SelectedCardId), Owner);
        await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Hand, Owner);
    }
}
