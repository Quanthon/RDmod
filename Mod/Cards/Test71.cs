using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test71 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<LowHandOverdrivePower>(8m)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    public Test71() : base(3, CardType.Power, CardRarity.Rare, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) =>
        await PowerCmd.Apply<LowHandOverdrivePower>(
            choiceContext, Owner.Creature,
            DynamicVars["LowHandOverdrivePower"].BaseValue,
            Owner.Creature, this);

    protected override void OnUpgrade() =>
        DynamicVars["LowHandOverdrivePower"].UpgradeValueBy(1m);
}
