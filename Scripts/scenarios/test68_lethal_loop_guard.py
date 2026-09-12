"""Regression: lethal Test68 resolution must not loop on unchanged Preparation."""

from __future__ import annotations

import time


TEST25 = "RD_MOD_CARD_TEST25"
TEST68 = "RD_MOD_CARD_TEST68"
TEST83 = "RD_MOD_CARD_TEST83"
DEFEND = "RD_MOD_CARD_DEFEND"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def run(test):
    test.enter_test_combat()
    test.run_console_command(
        "fight CULTISTS_NORMAL",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("energy 99", wait_for="play_card")

    add_card(test, TEST25)
    test.play_card(TEST25, wait_for="end_turn")
    assert not hand(test.refresh())

    for _ in range(2):
        add_card(test, TEST68)
        test.play_card(TEST68, wait_for="end_turn")
    test.run_console_command(f"power {PREPARATION} 2 0", wait_for="end_turn")

    add_card(test, TEST83)
    card = test.find_hand_card(TEST83)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    card = test.find_hand_card(TEST83)
    test.run_console_command(
        f"enchant SOULS_POWER 1 {card['index']}",
        wait_for="play_card",
    )
    for _ in range(9):
        add_card(test, DEFEND)

    before = test.refresh()
    assert len(hand(before)) == 10
    assert any(
        power["power_id"] == PREPARATION and int(power["amount"]) == 2
        for power in combat(before)["player"]["powers"]
    )

    started = time.monotonic()
    result = test.play_card(
        TEST83,
        wait_for=("play_card", "end_turn", "resolve_rewards"),
        timeout_seconds=20,
    )
    elapsed = time.monotonic() - started
    after = result["after"]
    assert "resolve_rewards" in after.action_names, (
        after.state.get("screen"),
        sorted(after.action_names),
    )
    return {
        "elapsed_seconds": round(elapsed, 3),
        "screen_after": after.state.get("screen"),
        "actions_after": sorted(after.action_names),
    }
