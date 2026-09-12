using System.Runtime.CompilerServices;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using RDmod.Mechanics;

namespace RDmod.Visuals;

public static class OverdriveCostGlow
{
    private const string ScenePath = "res://RDMod/Visuals/OverdriveCostGlow.tscn";
    private static readonly ConditionalWeakTable<NCard, GlowState> States = new();
    private static PackedScene? _scene;

    private sealed class GlowState
    {
        public TextureRect? Glow;
        public bool IsActive;
    }

    public static void Update(
        NCard cardNode,
        PileType pileType,
        CardPreviewMode previewMode)
    {
        GlowState state = States.GetOrCreateValue(cardNode);
        TextureRect? energyIcon = cardNode.GetNodeOrNull<TextureRect>("%EnergyIcon");

        bool shouldGlow =
            energyIcon is not null &&
            energyIcon.Visible &&
            pileType == PileType.Hand &&
            previewMode == CardPreviewMode.Normal &&
            cardNode.GetParent() is NHandCardHolder &&
            cardNode.Model?.Pile?.Type == PileType.Hand &&
            OverdriveRules.ShouldShowCostGlow(cardNode.Model);

        if (!shouldGlow || energyIcon is null)
        {
            Deactivate(state);
            return;
        }

        TextureRect? glow = EnsureGlow(state, cardNode, energyIcon);
        if (glow is null)
        {
            Deactivate(state);
            return;
        }

        SyncGlow(glow, energyIcon);

        if (!state.IsActive)
            Activate(state, glow);
    }

    private static TextureRect? EnsureGlow(
        GlowState state,
        NCard cardNode,
        TextureRect energyIcon)
    {
        if (state.Glow is not null && GodotObject.IsInstanceValid(state.Glow))
            return state.Glow;

        _scene ??= ResourceLoader.Load<PackedScene>(ScenePath);
        TextureRect glow = _scene.Instantiate<TextureRect>();
        glow.Set("active", false);
        glow.Visible = false;
        // Preserve the existing card-local draw order, including hand hover Z.
        cardNode.Body.AddChild(glow);
        cardNode.Body.MoveChild(glow, energyIcon.GetIndex());
        state.Glow = glow;
        state.IsActive = false;
        return glow;
    }

    private static void SyncGlow(TextureRect glow, TextureRect energyIcon)
    {
        float margin = glow.Get("glow_margin").AsSingle();
        glow.Position = energyIcon.Position - Vector2.One * margin;
        glow.Call("set_icon_size", energyIcon.Size);
    }

    private static void Activate(GlowState state, TextureRect glow)
    {
        state.IsActive = true;
        glow.Call("set_active", true);
    }

    private static void Deactivate(GlowState state)
    {
        if (!state.IsActive || state.Glow is null ||
            !GodotObject.IsInstanceValid(state.Glow))
            return;

        state.IsActive = false;
        state.Glow.Call("set_active", false);
    }
}
