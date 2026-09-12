using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Characters;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test32 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<StrengthPower>(1m),
        ModCardVars.Computed(
            "CalculatedStrength",
            0,
            card => card?.Owner.PlayerCombatState is null
                ? 0
                : PileType.Hand.GetPile(card.Owner).Cards.Count(handCard => handCard.Type == CardType.Status)
                    * card.DynamicVars.Strength.BaseValue)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromPower<StrengthPower>()];

    public Test32() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        List<CardModel> statuses = PileType.Hand.GetPile(Owner).Cards
            .Where(card => card.Type == CardType.Status)
            .ToList();
        foreach (CardModel status in statuses)
            await CardCmd.Exhaust(choiceContext, status);

        if (statuses.Count > 0)
        {
            await PowerCmd.Apply<StrengthPower>(
                choiceContext, Owner.Creature,
                DynamicVars.Strength.BaseValue * statuses.Count,
                Owner.Creature, this);
        }
    }

    protected override void OnUpgrade() => AddKeyword(CardKeyword.Retain);
}
