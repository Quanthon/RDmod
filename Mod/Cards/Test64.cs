using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using RDmod.Characters;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Cards;

[RegisterCard(typeof(RainbowDashCardPool))]
public sealed class Test64 : ModCardTemplate
{
    public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [RDmod.Mechanics.KeywordHoverTips.Preparation, RDmod.Mechanics.KeywordHoverTips.Flight];

    public Test64() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self) { }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        int preparation = Owner.Creature.GetPower<PreparationPower>()?.Amount ?? 0;
        int flight = Owner.Creature.GetPower<FlightPower>()?.Amount ?? 0;

        if (preparation < flight)
        {
            await PowerCmd.Apply<PreparationPower>(
                choiceContext, Owner.Creature, flight - preparation, Owner.Creature, this);
        }
        else if (flight < preparation)
        {
            await PowerCmd.Apply<FlightPower>(
                choiceContext, Owner.Creature, preparation - flight, Owner.Creature, this);
        }
    }

    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}
