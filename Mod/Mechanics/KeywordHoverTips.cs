using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;

namespace RDmod.Mechanics;

public static class KeywordHoverTips
{
    public static IHoverTip Preparation => Create("RD_MOD_PREPARATION_KEYWORD");
    public static IHoverTip Flight => Create("RD_MOD_FLIGHT_KEYWORD");

    public static IHoverTip Overdrive(AbstractModel source)
    {
        LocString description = new("static_hover_tips", "RD_MOD_OVERDRIVE_KEYWORD.description");
        description.Add("energyPrefix", EnergyIconHelper.GetPrefix(source));
        return new HoverTip(new LocString("static_hover_tips", "RD_MOD_OVERDRIVE_KEYWORD.title"), description);
    }

    private static IHoverTip Create(string key) => new HoverTip(
        new LocString("static_hover_tips", key + ".title"),
        new LocString("static_hover_tips", key + ".description"));
}
