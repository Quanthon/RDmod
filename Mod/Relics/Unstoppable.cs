using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using RDmod.Characters;
using RDmod.Mechanics;
using RDmod.Powers;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Relics;

[RegisterRelic(typeof(RainbowDashRelicPool))]
public sealed class Unstoppable : ModRelicTemplate
{
    public override RelicRarity Rarity => RelicRarity.Ancient;

    public override RelicAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/relics/Unstoppable_icon.png",
        IconOutlinePath: "res://RDMod/images/relics/Unstoppable_outline.png",
        BigIconPath: "res://RDMod/images/relics/Unstoppable.png"
    );

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new PowerVar<OverdrivePower>(2m)
    ];

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        OverdriveRules.GetKeywordHoverTips(this);

    public override async Task AfterEnergyReset(Player player)
    {
        if (player != Owner)
            return;
        Flash();
        await PowerCmd.Apply<OverdrivePower>(
            new ThrowingPlayerChoiceContext(),
            Owner.Creature,
            DynamicVars["OverdrivePower"].BaseValue,
            Owner.Creature,
            null
        );
    }
}
