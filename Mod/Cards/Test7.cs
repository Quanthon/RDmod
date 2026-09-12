using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test7 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(6m, ValueProp.Move),
        // RDDesign: base[1], upgrade[1]
        new DynamicVar("AttackRepeat", 2m),
        // RDDesign: base[2], upgrade[2]
        new DamageVar("SelfDamage", 1m,
            ValueProp.Unpowered | ValueProp.Move),
        // RDDesign: base[3], upgrade[3]
        new DynamicVar("SelfDamageRepeat", 2m)
    ];

    public Test7() : base(1, CardType.Attack, CardRarity.Common, TargetType.AllEnemies)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .WithHitCount(DynamicVars["AttackRepeat"].IntValue)
            .FromCard(this, cardPlay)
            .TargetingAllOpponents(CombatState!)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(choiceContext);

        for (int i = 0; i < DynamicVars["SelfDamageRepeat"].IntValue; i++)
        {
            await CreatureCmd.Damage(choiceContext, Owner.Creature,
                (DamageVar)DynamicVars["SelfDamage"], this, cardPlay);
        }
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(2m);
    }
}
