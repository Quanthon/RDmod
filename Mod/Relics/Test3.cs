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
public sealed class Test3 : ModRelicTemplate
{
    public override RelicRarity Rarity => RelicRarity.Common;
    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Test3_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Test3_outline.png",
        BigIconPath: "res://RDMod/images/relics/Test3.png");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<FlightPower>(1m)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [RDmod.Mechanics.KeywordHoverTips.Flight];
    public override async Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (creature != Owner.Creature || delta >= 0 || !CombatManager.Instance.IsInProgress || creature.IsDead) return;
        Flash();
        await PowerCmd.Apply<FlightPower>(new ThrowingPlayerChoiceContext(), creature, DynamicVars["FlightPower"].BaseValue, creature, null);
    }
}
