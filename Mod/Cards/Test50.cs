using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using RDmod.Characters;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test50 : ModCardTemplate
{
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new PowerVar<CardSelfDamageStrengthPower>(1m)
    ];
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public Test50() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) =>
        await PowerCmd.Apply<CardSelfDamageStrengthPower>(choiceContext, Owner.Creature, DynamicVars["CardSelfDamageStrengthPower"].BaseValue, Owner.Creature, this);
    protected override void OnUpgrade() => DynamicVars["CardSelfDamageStrengthPower"].UpgradeValueBy(1m);
}
