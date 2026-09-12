using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class DaringDoRob : ModCardTemplate
{
    public override bool CanBeGeneratedInCombat => false;
    public override bool CanBeGeneratedByModifiers => false;
    public override CardAssetProfile AssetProfile => new(PortraitPath: "res://RDMod/images/cards/DaringDoRob.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("EnemyStrengthLoss", 3m),
        // RDDesign: base[1], upgrade[1]
        new PowerVar<StrengthPower>(3m)
    ];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [HoverTipFactory.FromPower<StrengthPower>()];
    public DaringDoRob() : base(2, CardType.Skill, CardRarity.Token, TargetType.AnyEnemy) { }
    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        ArgumentNullException.ThrowIfNull(cardPlay.Target);
        await PowerCmd.Apply<StrengthPower>(choiceContext, cardPlay.Target, -DynamicVars["EnemyStrengthLoss"].BaseValue, Owner.Creature, this);
        await PowerCmd.Apply<StrengthPower>(choiceContext, Owner.Creature, DynamicVars["StrengthPower"].BaseValue, Owner.Creature, this);
    }
    protected override void OnUpgrade()
    {
        DynamicVars["EnemyStrengthLoss"].UpgradeValueBy(1m);
        DynamicVars["StrengthPower"].UpgradeValueBy(1m);
    }
}
