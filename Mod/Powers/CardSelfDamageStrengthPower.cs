using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class CardSelfDamageStrengthPower : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/CardSelfDamageStrengthPower.png",
        BigIconPath: "res://RDMod/images/powers/CardSelfDamageStrengthPower.png");
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override async Task AfterDamageReceived(
        PlayerChoiceContext choiceContext,
        Creature target,
        DamageResult result,
        ValueProp props,
        Creature? dealer,
        CardModel? cardSource)
    {
        if (target != Owner ||
            result.TotalDamage <= 0 ||
            cardSource is null ||
            cardSource.Owner.Creature != Owner)
            return;

        Flash();
        await PowerCmd.Apply<StrengthPower>(choiceContext, Owner, Amount, Owner, null);
    }
}
