using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Content;

namespace RDmod.Powers;

[RegisterPower]
public sealed class Test68Power : ModPowerTemplate
{

    public override PowerAssetProfile AssetProfile => new(
        IconPath: "res://RDMod/images/powers/Test68Power.png",
        BigIconPath: "res://RDMod/images/powers/Test68Power.png");
    private sealed class Data
    {
        public bool IsConfigured;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override object InitInternalData() => new Data();

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new DynamicVar("PreparationThreshold", 0m),
        new DynamicVar("PreparationCost", 0m),
        new DynamicVar("DamagePerStack", 0m),
        new DynamicVar("EnergyPerStack", 0m)
    ];

    public void Configure(
        int preparationThreshold,
        int preparationCost,
        decimal damagePerStack,
        int energyPerStack)
    {
        AssertMutable();
        DynamicVars["PreparationThreshold"].BaseValue = preparationThreshold;
        DynamicVars["PreparationCost"].BaseValue = preparationCost;
        DynamicVars["DamagePerStack"].BaseValue = damagePerStack;
        DynamicVars["EnergyPerStack"].BaseValue = energyPerStack;
        GetInternalData<Data>().IsConfigured = true;
    }

    public override async Task AfterPowerAmountChanged(
        PlayerChoiceContext choiceContext,
        PowerModel power,
        decimal amount,
        Creature? applier,
        CardModel? cardSource)
    {
        if (power is PreparationPower &&
            power.Owner == Owner &&
            amount > 0)
        {
            await ResolvePreparation(choiceContext);
        }
    }

    public async Task ResolvePreparation(PlayerChoiceContext choiceContext)
    {
        if (Owner.Player is not { } player ||
            !GetInternalData<Data>().IsConfigured)
        {
            return;
        }

        int preparationThreshold =
            DynamicVars["PreparationThreshold"].IntValue;
        int preparationCost = DynamicVars["PreparationCost"].IntValue;
        decimal damage =
            DynamicVars["DamagePerStack"].BaseValue * Amount;
        int energy =
            DynamicVars["EnergyPerStack"].IntValue * (int)Amount;

        if (preparationThreshold <= 0 || preparationCost <= 0)
        {
            return;
        }

        PreparationPower? preparation = Owner.GetPower<PreparationPower>();
        while (!CombatManager.Instance.IsEnding &&
               preparation is not null &&
               preparation.Amount >= preparationThreshold)
        {
            int previousAmount = preparation.Amount;
            int currentAmount = await PowerCmd.ModifyAmount(
                choiceContext,
                preparation,
                -preparationCost,
                Owner,
                cardSource: null);
            if (currentAmount >= previousAmount)
            {
                break;
            }

            Flash();
            await CreatureCmd.Damage(
                choiceContext,
                CombatState.HittableEnemies,
                damage,
                ValueProp.Unpowered,
                Owner);
            await PlayerCmd.GainEnergy(energy, player);

            if (CombatManager.Instance.IsEnding)
            {
                break;
            }

            preparation = Owner.GetPower<PreparationPower>();
        }
    }
}
