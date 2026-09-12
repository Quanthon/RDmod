using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test46 : ModCardTemplate
{
    public override IEnumerable<CardKeyword> CanonicalKeywords =>
        [CardKeyword.Sly, CardKeyword.Exhaust];
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<FlightPower>(4m)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Flight];

    public Test46() : base(3, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) =>
        await PowerCmd.Apply<FlightPower>(
            choiceContext, Owner.Creature,
            DynamicVars["FlightPower"].BaseValue,
            Owner.Creature, this);

    protected override void OnUpgrade() =>
        DynamicVars["FlightPower"].UpgradeValueBy(2m);
}
