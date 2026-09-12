using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models.Powers;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test58 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars => [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<FlightPower>(10m), 
        // RDDesign: base[1], upgrade[1]
        new PowerVar<NoBlockPower>(3m)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [RDmod.Mechanics.KeywordHoverTips.Flight, HoverTipFactory.FromPower<NoBlockPower>()];
    public Test58() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await PowerCmd.Apply<FlightPower>(choiceContext, Owner.Creature, DynamicVars["FlightPower"].BaseValue, Owner.Creature, this);
        await PowerCmd.Apply<NoBlockPower>(choiceContext, Owner.Creature, DynamicVars["NoBlockPower"].BaseValue, Owner.Creature, this);
    }

    protected override void OnUpgrade() => DynamicVars["FlightPower"].UpgradeValueBy(2m);
}
