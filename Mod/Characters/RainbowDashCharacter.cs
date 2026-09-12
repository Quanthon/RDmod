using Godot;
using MegaCrit.Sts2.Core.Entities.Characters;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Scaffolding.Characters;
using STS2RitsuLib.Scaffolding.Godot;
using STS2RitsuLib.Scaffolding.Visuals.StateMachine;
using RDmod.Cards;
using RDmod.Powers;
using TakeOffCard = RDmod.Cards.TakeOff;

namespace RDmod.Characters;

[RegisterCharacter]
public class RainbowDashCharacter : ModCharacterTemplate<RainbowDashCardPool, RainbowDashRelicPool, RainbowDashPotionPool>
{
    public override Color NameColor => new(0.298f, 0.788f, 1f);
    public override Color EnergyLabelOutlineColor => new("163E64FF");
    public override Color MapDrawingColor => new(0.298f, 0.788f, 1f);

    public override CharacterGender Gender => CharacterGender.Feminine;

    public override int StartingHp => 70;
    public override int StartingGold => 99;

    public override CharacterAssetProfile AssetProfile => CharacterAssetProfiles.Merge(
        CharacterAssetProfiles.Silent(),
        new(
            Scenes: new(
                VisualsPath: "res://Characters/RainbowDashVisuals.tscn",
                EnergyCounterPath: "res://scenes/combat/energy_counters/defect_energy_counter.tscn",
                MerchantAnimPath: "res://Characters/RainbowDashMerchant.tscn",
                RestSiteAnimPath: "res://Characters/RainbowDashRestSite.tscn"
            ),
            Ui: new(
                IconTexturePath: "res://RDMod/images/characters/ui/character_icon.png",
                IconOutlineTexturePath: "res://RDMod/images/characters/ui/character_icon_outline.png",
                IconPath: "res://Characters/RainbowDashIcon.tscn",
                CharacterSelectBgPath: "res://Characters/RainbowDashCharacterSelectBg.tscn",
                CharacterSelectIconPath: "res://RDMod/images/characters/ui/char_select_silent.png",
                CharacterSelectLockedIconPath: "res://RDMod/images/characters/ui/char_select_silent.png",
                CharacterSelectTransitionPath: "res://RDMod/materials/transitions/rainbow_dash_transition_mat.tres",
                MapMarkerPath: "res://RDMod/images/characters/ui/map_marker.png"
            ),
            Vfx: new(
                TrailPath: "res://scenes/vfx/card_trail_defect.tscn"
            ),
            Audio: new(
                CharacterSelectSfx: "res://RDMod/audio/select_hover.mp3"
            ),
            Multiplayer: new(
                ArmPointingTexturePath: "res://RDMod/images/characters/ui/multiplayer_hand_point.png",
                ArmRockTexturePath: "res://RDMod/images/characters/ui/multiplayer_hand_rock.png",
                ArmPaperTexturePath: "res://RDMod/images/characters/ui/multiplayer_hand_paper.png",
                ArmScissorsTexturePath: "res://RDMod/images/characters/ui/multiplayer_hand_scissors.png"
            )
        ));


    public override string? PlaceholderCharacterId => null;

    public override float AttackAnimDelay => 0.1f;
    public override float CastAnimDelay => 0f;

    public override bool RequiresEpochAndTimeline => false;

    protected override NCreatureVisuals? TryCreateCreatureVisuals() =>
        RitsuGodotNodeFactories.CreateFromScenePath<NCreatureVisuals>(AssetProfile.Scenes!.VisualsPath!);

    protected override ModAnimStateMachine? SetupCustomCombatAnimationStateMachine(
        Node visualsRoot,
        CharacterModel character)
    {
        bool HasFlight() =>
            FindCreatureNode(visualsRoot)?.Entity.GetPower<FlightPower>() is { Amount: > 0 };

        var builder = ModAnimStateMachineBuilder.Create();

        var idle = builder.AddState("idle", loop: true);
        if (!HasFlight())
            idle.AsInitial();
        idle.Done();

        var flyingIdle = builder.AddState("flying_idle", loop: true);
        if (HasFlight())
            flyingIdle.AsInitial();
        flyingIdle.Done();

        builder
            .AddState("attack").WithNext("idle").Done()
            .AddState("flying_attack").WithNext("flying_idle").Done()
            .AddState("hit").WithNext("idle").Done()
            .AddState("flying_hit").WithNext("flying_idle").Done()
            .AddState("take_off").WithNext("flying_idle").Done()
            .AddState("land").WithNext("idle").Done()
            .AddState("dead").Done();

        builder.AddAnyState("Idle", "flying_idle", HasFlight);
        builder.AddAnyState("Idle", "idle", () => !HasFlight());
        builder.AddAnyState("Attack", "flying_attack", HasFlight);
        builder.AddAnyState("Attack", "attack", () => !HasFlight());
        builder.AddAnyState("Hit", "flying_hit", HasFlight);
        builder.AddAnyState("Hit", "hit", () => !HasFlight());
        builder.AddAnyState("Cast", "flying_idle", HasFlight);
        builder.AddAnyState("Cast", "idle", () => !HasFlight());
        builder.AddAnyState("Relaxed", "flying_idle", HasFlight);
        builder.AddAnyState("Relaxed", "idle", () => !HasFlight());
        builder.AddAnyState("FlightOn", "take_off");
        builder.AddAnyState("FlightOff", "land");
        builder.AddAnyState("Dead", "dead");

        return builder.BuildForVisualsRoot(visualsRoot, character);
    }

    private static NCreature? FindCreatureNode(Node node)
    {
        for (Node? current = node; current is not null; current = current.GetParent())
        {
            if (current is NCreature creature)
                return creature;
        }

        return null;
    }

    protected override IEnumerable<StartingDeckEntry> StartingDeckEntries =>
    [
        new(typeof(Strike), 4),
        new(typeof(Defend), 4),
        new(typeof(Charge), 1),
        new(typeof(TakeOffCard), 1)
    ];

    public override List<string> GetArchitectAttackVfx() =>
    [
        "vfx/vfx_attack_blunt",
        "vfx/vfx_heavy_blunt",
        "vfx/vfx_attack_slash",
        "vfx/vfx_bloody_impact",
        "vfx/vfx_rock_shatter"
    ];
}
