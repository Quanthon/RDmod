using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using STS2RitsuLib.Cards.DynamicVars;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test88 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(3m, ValueProp.Move),
        ModCardVars.Computed("CalculatedHits", 0,
            card => card?.Owner.PlayerCombatState is null ? 0 :
                PileType.Hand.GetPile(card.Owner).Cards.Count(other => other != card))
    ];

    public Test88() : base(0, CardType.Attack, CardRarity.Rare, TargetType.RandomEnemy)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        List<CardModel> cards = PileType.Hand.GetPile(Owner).Cards.ToList();
        await CardCmd.Discard(choiceContext, cards);

        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .WithHitCount(cards.Count)
            .FromCard(this, cardPlay)
            .TargetingRandomOpponents(CombatState!)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(choiceContext);
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(1m);
    }
}
