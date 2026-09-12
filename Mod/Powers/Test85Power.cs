using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using RDmod.Cards;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class Test85Power : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/Test85Power.png",
        BigIconPath: "res://RDMod/images/powers/Test85Power.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> AdditionalHoverTips =>
        [HoverTipFactory.FromCard<AppleCider>()];

    public override async Task BeforeHandDraw(
        Player player,
        PlayerChoiceContext choiceContext,
        ICombatState combatState)
    {
        if (player != Owner.Player)
            return;

        Flash();
        await CardGenerationOperations.AddAppleCidersToHand(
            combatState,
            player,
            Amount);
    }
}
