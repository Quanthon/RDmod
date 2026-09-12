using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test18 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DamageVar(7m, ValueProp.Move),
        // RDDesign: base[1], upgrade[1]
        new PowerVar<WeakPower>(2m)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation, HoverTipFactory.FromPower<WeakPower>()];

    private bool HasPreparation =>
        Owner.Creature.GetPower<PreparationPower>() is { Amount: > 0 };

    protected override bool ShouldGlowGoldInternal => HasPreparation;

    public Test18() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy)
    {
    }

    protected override async Task OnPlay(
        PlayerChoiceContext choiceContext,
        CardPlay cardPlay)
    {
        ArgumentNullException.ThrowIfNull(cardPlay.Target);

        await DamageCmd.Attack(DynamicVars.Damage.BaseValue)
            .FromCard(this, cardPlay)
            .Targeting(cardPlay.Target)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(choiceContext);

        if (HasPreparation)
        {
            await PowerCmd.Apply<WeakPower>(choiceContext, cardPlay.Target,
                DynamicVars["WeakPower"].BaseValue, Owner.Creature, this);
        }
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(1m);
        DynamicVars["WeakPower"].UpgradeValueBy(1m);
    }
}
