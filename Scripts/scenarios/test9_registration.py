"""Runtime assertions for the completed Test9 registration and upgrade."""

from __future__ import annotations


CARD_ID = "RD_MOD_CARD_TEST9"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def flight_amount(snapshot):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == FLIGHT), 0)


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"card {CARD_ID}", wait_for="play_card")

    card = test.find_hand_card(CARD_ID)
    assert int(card["energy_cost"]) == 2, card
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(CARD_ID)
    assert upgraded["upgraded"] and int(upgraded["energy_cost"]) == 2, upgraded

    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card(CARD_ID)
    after = test.refresh()
    block_gained = int(combat(after)["player"]["block"]) - block_before
    assert block_gained == 10, ("Test9 upgraded block", block_gained)
    assert flight_amount(after) == 4, ("Test9 upgraded Flight", combat(after)["player"]["powers"])
    return {
        "test9_upgraded_cost": 2,
        "test9_upgraded_block": block_gained,
        "test9_upgraded_flight": flight_amount(after),
    }
