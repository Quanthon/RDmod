"""Runtime assertion that Test55 grants Entropic Brew on Fatal."""

from __future__ import annotations


CARD_ID = "RD_MOD_CARD_TEST55"
POTION_ID = "ENTROPIC_BREW"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def contains_value(value, expected):
    if isinstance(value, dict):
        return any(contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return value == expected


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    before = test.refresh()
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    test.run_console_command(
        f"damage {enemy_hp - 1} 1", wait_for="play_card"
    )
    test.run_console_command(f"card {CARD_ID}", wait_for="play_card")
    test.play_card(CARD_ID, target_index=0)
    after = test.refresh()
    assert contains_value(after.state, POTION_ID), after.state.get("run")
    return {"test55_fatal_potion": POTION_ID}
