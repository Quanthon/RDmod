using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Characters;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test25 : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        ModCardVars.Computed(
            "CalculatedCards",
            0,
            card => card?.Owner.PlayerCombatState is null
                ? 0
                : PileType.Hand.GetPile(card.Owner).Cards.Count(handCard => handCard != card))
    ];
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    public Test25() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        IReadOnlyList<CardModel> cards = PileType.Hand
            .GetPile(Owner)
            .Cards
            .ToList();

        await CardCmd.Discard(choiceContext, cards);
        if (cards.Count > 0)
        {
            await PowerCmd.Apply<DrawCardsNextTurnPower>(
                choiceContext,
                Owner.Creature,
                cards.Count,
                Owner.Creature,
                this
            );
        }
    }

    protected override void OnUpgrade()
    {
        EnergyCost.UpgradeBy(-1);
    }
}

