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
public sealed class Test83 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    public override IEnumerable<CardKeyword> CanonicalKeywords =>
        [CardKeyword.Exhaust];

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<PreparationPower>(1m)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation];

    public Test83() : base(
        1,
        CardType.Skill,
        CardRarity.Uncommon,
        TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        List<CardModel> cards = PileType.Hand.GetPile(Owner).Cards.ToList();
        foreach (CardModel card in cards)
            await CardCmd.Exhaust(choiceContext, card);

        if (cards.Count > 0)
        {
            await PowerCmd.Apply<PreparationPower>(
                choiceContext,
                Owner.Creature,
                cards.Count * DynamicVars["PreparationPower"].BaseValue,
                Owner.Creature,
                this);
        }
    }

    protected override void OnUpgrade() =>
        DynamicVars["PreparationPower"].UpgradeValueBy(1m);
}
