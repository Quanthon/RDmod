using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using RDmod.Mechanics;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class TurnOverdrivePower : ModPowerTemplate
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override IEnumerable<IHoverTip> AdditionalHoverTips => OverdriveRules.GetKeywordHoverTips(this);

    public override async Task AfterEnergyReset(Player player)
    {
        if (player != Owner.Player)
            return;
        Flash();
        await PowerCmd.Apply<OverdrivePower>(new ThrowingPlayerChoiceContext(), Owner, Amount, Owner, null);
    }
}
