"""Runtime assertions for player-visible calculated damage text."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"power {FLIGHT} 3 0", wait_for="play_card")
    test.run_console_command("card RD_MOD_CARD_TEST23", wait_for="play_card")
    test23 = test.find_hand_card("RD_MOD_CARD_TEST23")
    assert "造成12点伤害" in test23["resolved_rules_text"], test23["resolved_rules_text"]

    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"power {PREPARATION} 2 0", wait_for="play_card")
    test.run_console_command(f"power {FLIGHT} 3 0", wait_for="play_card")
    test.run_console_command("card RD_MOD_CARD_TEST51", wait_for="play_card")
    test51 = test.find_hand_card("RD_MOD_CARD_TEST51")
    test.run_console_command(f"upgrade {test51['index']}", wait_for="play_card")
    test51 = test.find_hand_card("RD_MOD_CARD_TEST51")
    assert "造成72点伤害" in test51["resolved_rules_text"], test51["resolved_rules_text"]
    return {
        "test23_text": test23["resolved_rules_text"],
        "test51_text": test51["resolved_rules_text"],
    }
