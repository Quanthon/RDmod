using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test59 : ModCardTemplate
{
    // RDDesign: base[0], upgrade[0], localization[0]
    private const int GeneratedCardDiscount = 1;
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public Test59() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self) { }

    protected override Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        HashSet<CardModel> generatedCards = CardTurnStatistics.GeneratedCards();
        foreach (CardModel card in Owner.PlayerCombatState!.AllCards.Where(generatedCards.Contains))
            card.EnergyCost.AddThisCombat(-GeneratedCardDiscount, reduceOnly: true);
        return Task.CompletedTask;
    }

    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}
