using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test35 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(
        PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [
        // RDDesign: base[0], upgrade[0]
        new DynamicVar("DiscardCount", 1m),
        // RDDesign: base[1], upgrade[1]
        new PowerVar<OverdrivePower>(1m)];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    public Test35() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await CardSelectionOperations.DiscardFromHand(
            choiceContext,
            Owner,
            DynamicVars["DiscardCount"].IntValue,
            this);

        await PowerCmd.Apply<OverdrivePower>(
            choiceContext,
            Owner.Creature,
            DynamicVars["OverdrivePower"].BaseValue,
            Owner.Creature,
            this
        );
    }

    protected override void OnUpgrade() => AddKeyword(CardKeyword.Retain);
}
