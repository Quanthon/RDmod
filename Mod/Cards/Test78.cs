using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test78 : ModCardTemplate
{
    protected override bool HasEnergyCostX => true;
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesignManualUpgrade: upgrade[0] - Base count is X and has no numeric description target.
        new DynamicVar("BonusCards", 0m)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromCard<AppleCider>(), EnergyHoverTip];

    public Test78() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        int energy = ResolveEnergyXValue();
        int count = energy + DynamicVars["BonusCards"].IntValue;
        await CardGenerationOperations.AddAppleCidersToHand(this, count);
        if (energy > 0)
            await PowerCmd.Apply<EnergyNextTurnPower>(choiceContext, Owner.Creature, energy, Owner.Creature, this);
    }

    protected override void OnUpgrade() =>
        DynamicVars["BonusCards"].UpgradeValueBy(1m);
}
