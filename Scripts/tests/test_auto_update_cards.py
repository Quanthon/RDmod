from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from auto_update_cards import KeyUpdateResult, orchestrate  # noqa: E402


def diff(*, added: tuple[str, ...] = (), removed: tuple[str, ...] = (), changed: tuple[str, ...] = ()):
    return {
        "added": [{"key": key} for key in added],
        "removed": [{"key": key} for key in removed],
        "changed": [{"key": key} for key in changed],
        "possibleRenames": [],
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "possibleRenames": 0,
        },
    }


class AutoUpdateCardsTests(unittest.TestCase):
    def test_automatic_batch_requires_validation_before_snapshot_acceptance(self) -> None:
        report = orchestrate(
            diff(changed=("First", "Second")),
            lambda key: KeyUpdateResult(key, ("费用",)),
        )

        self.assertEqual(report["summary"]["autoUpdated"], 2)
        self.assertFalse(report["summary"]["snapshotUpdated"])
        self.assertEqual(report["manualRequired"][0]["key"], "<snapshot>")

    def test_partial_batch_applies_safe_keys_but_does_not_accept(self) -> None:
        def apply(key: str) -> KeyUpdateResult:
            if key == "Manual":
                return KeyUpdateResult(key, error="描述结构变化")
            return KeyUpdateResult(key, ("费用",))

        report = orchestrate(
            diff(changed=("Safe", "Manual")),
            apply,
        )

        self.assertEqual([item["key"] for item in report["autoUpdated"]], ["Safe"])
        self.assertEqual(report["manualRequired"][0]["key"], "Manual")
        self.assertFalse(report["summary"]["snapshotUpdated"])

    def test_addition_blocks_snapshot_without_preventing_safe_changes(self) -> None:
        report = orchestrate(
            diff(added=("NewCard",), changed=("Safe",)),
            lambda key: KeyUpdateResult(key, ("费用",)),
        )

        self.assertEqual(report["summary"]["autoUpdated"], 1)
        self.assertEqual(report["manualRequired"][0]["key"], "NewCard")

    def test_no_changes_does_not_rewrite_snapshot(self) -> None:
        report = orchestrate(
            diff(),
            lambda key: KeyUpdateResult(key),
        )

        self.assertEqual(report["summary"]["total"], 0)
        self.assertFalse(report["summary"]["snapshotUpdated"])


if __name__ == "__main__":
    unittest.main()
