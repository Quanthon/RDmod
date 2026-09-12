using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Relics;

[RegisterRelic(typeof(RainbowDashRelicPool))]
public sealed class Test6 : ModRelicTemplate
{
    public override RelicRarity Rarity => RelicRarity.Rare;
    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Test6_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Test6_outline.png",
        BigIconPath: "res://RDMod/images/relics/Test6.png");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new GoldVar(60), new DynamicVar("GoldReduction", 20m)];
    private int _turnsEnded;
    public override bool ShowCounter => true;
    public override int DisplayAmount => Math.Max(0, DynamicVars.Gold.IntValue - _turnsEnded * DynamicVars["GoldReduction"].IntValue);
    public override Task BeforeCombatStart()
    {
        AssertMutable();
        _turnsEnded = 0;
        InvokeDisplayAmountChanged();
        return Task.CompletedTask;
    }
    public override Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner.Creature))
        {
            AssertMutable();
            _turnsEnded++;
            InvokeDisplayAmountChanged();
        }
        return Task.CompletedTask;
    }
    public override Task AfterCombatEnd(CombatRoom room)
    {
        if (DisplayAmount > 0)
        {
            Flash();
            room.AddExtraReward(Owner, new GoldReward(DisplayAmount, Owner));
        }
        return Task.CompletedTask;
    }
}
