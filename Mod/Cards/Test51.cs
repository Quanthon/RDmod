using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test51 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new CalculationBaseVar(12m),
        // RDDesign: base[1], upgrade[1]
        new ExtraDamageVar(6m),
        new CalculatedDamageVar(ValueProp.Move).WithMultiplier(
            static (CardModel card, Creature? _) => ResourceLayers(card))
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation, RDmod.Mechanics.KeywordHoverTips.Flight];

    public Test51() : base(2, CardType.Attack, CardRarity.Rare, TargetType.AllEnemies) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        int resourceLayers = ResourceLayers(this);
        decimal damage = DynamicVars.CalculationBase.BaseValue
            + DynamicVars.ExtraDamage.BaseValue * resourceLayers;

        await DamageCmd.Attack(damage)
            .FromCard(this, cardPlay)
            .TargetingAllOpponents(CombatState!)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(choiceContext);

        await ConsumePower<PreparationPower>(choiceContext);
        await ConsumePower<FlightPower>(choiceContext);
    }

    protected override void OnUpgrade()
    {
        DynamicVars.CalculationBase.UpgradeValueBy(4m);
        DynamicVars.ExtraDamage.UpgradeValueBy(2m);
    }

    private static int ResourceLayers(CardModel card) =>
        Math.Max(card.Owner.Creature.GetPower<PreparationPower>()?.Amount ?? 0, 0)
        + Math.Max(card.Owner.Creature.GetPower<FlightPower>()?.Amount ?? 0, 0);

    private async Task ConsumePower<T>(PlayerChoiceContext choiceContext)
        where T : PowerModel
    {
        T? power = Owner.Creature.GetPower<T>();
        if (power is null || power.Amount <= 0)
            return;

        await PowerCmd.ModifyAmount(
            choiceContext, power, -power.Amount, Owner.Creature, this);
    }
}
