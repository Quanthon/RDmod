"""Inspect whether STS2-Agent exposes native card glow state."""

from __future__ import annotations


CARD = "RD_MOD_CARD_TEST4"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def run(test):
    test.enter_test_combat()
    test.run_console_command(f"card {CARD}", wait_for="play_card")
    before = test.find_hand_card(CARD)
    test.run_console_command(f"power {PREPARATION} 1 0", wait_for="play_card")
    after = test.find_hand_card(CARD)
    return {
        "card_keys": sorted(after),
        "before": before,
        "after": after,
    }
