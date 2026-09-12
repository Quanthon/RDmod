using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using STS2RitsuLib.Interop.AutoRegistration;
using STS2RitsuLib.Models.Capabilities;

namespace RDmod.Capabilities;

[RegisterModelCapability]
public sealed class TemporaryCardOverdriveCapability :
    TurnLimitedCapability<CardModel>,
    ICardDescriptionContributor
{
    public IEnumerable<CardDescriptionFragment> GetDescriptionFragments(
        CardDescriptionContext context) =>
    [
        new CardDescriptionFragment(
            new LocString("cards", $"{Id.Entry}.description"),
            CardDescriptionFragmentPlacement.AfterBase
        )
    ];
}
