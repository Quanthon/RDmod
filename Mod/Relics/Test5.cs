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
public sealed class Test5 : ModRelicTemplate
{
    public override RelicRarity Rarity => RelicRarity.Uncommon;
    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Test5_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Test5_outline.png",
        BigIconPath: "res://RDMod/images/relics/Test5.png");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<PreparationPower>(1m)];
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => [RDmod.Mechanics.KeywordHoverTips.Preparation];
    public override bool TryModifyPowerAmountReceived(PowerModel canonicalPower, Creature target, decimal amount, Creature? applier, out decimal modifiedAmount)
    {
        modifiedAmount = amount;
        if (canonicalPower is not PreparationPower || target != Owner.Creature || amount <= 0) return false;
        modifiedAmount += DynamicVars["PreparationPower"].BaseValue;
        return true;
    }
}
