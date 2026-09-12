using Godot;
using STS2RitsuLib.Scaffolding.Content;
using STS2RitsuLib.Utils;

namespace RDmod.Characters;

public class RainbowDashCardPool : TypeListCardPoolModel
{
    public override string Title => "rainbow_dash";
    public override string EnergyColorName => "defect";

    public override Color DeckEntryCardColor => new(0.298f, 0.788f, 1f);
    public override Color EnergyOutlineColor => new("1D5673");

    private static readonly Material? RainbowFrameMaterial =
        MaterialUtils.CreateReplaceHueShaderMaterial(0.298f, 0.788f, 1f);

    public override Material? PoolFrameMaterial => RainbowFrameMaterial;
    public override bool IsColorless => false;
}

public class RainbowDashRelicPool : TypeListRelicPoolModel
{
    public override string EnergyColorName => "defect";
}

public class RainbowDashPotionPool : TypeListPotionPoolModel
{
    public override string EnergyColorName => "defect";
}
