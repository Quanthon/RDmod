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
public sealed class Test4 : ModRelicTemplate
{
    public override RelicRarity Rarity => RelicRarity.Rare;
    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Test4_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Test4_outline.png",
        BigIconPath: "res://RDMod/images/relics/Test4.png");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(1)];
    public override async Task BeforeCombatStart()
    {
        Flash();
        for (int i = 0; i < DynamicVars.Cards.IntValue; i++)
            await DaringDoCards.AddRandomToHand(Owner);
    }
}
