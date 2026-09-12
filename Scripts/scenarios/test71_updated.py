"""Runtime assertions for Test71's upgraded threshold and Status exclusion."""

from __future__ import annotations


CARD = "RD_MOD_CARD_TEST71"
STRIKE = "RD_MOD_CARD_STRIKE"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"
POWER = "RD_MOD_POWER_LOW_HAND_OVERDRIVE_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    return next(
        (
            int(power["amount"])
            for power in combat(snapshot)["player"]["powers"]
            if power["power_id"] == power_id
        ),
        0,
    )


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    add_card(test, CARD)
    card = test.find_hand_card(CARD)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(CARD)
    assert int(upgraded["energy_cost"]) == 1
    test.play_card(CARD)
    assert power_amount(test.refresh(), POWER) == 3

    add_card(test, "RD_MOD_CARD_TEST33")
    test.play_card("RD_MOD_CARD_TEST33", wait_for="end_turn")
    for _ in range(4):
        add_card(test, STRIKE)
    test.play_card(STRIKE, target_index=0, wait_for="end_turn")
    while hand(test.refresh()):
        snapshot = test.refresh()
        test.run_console_command(
            f"remove_card {hand(snapshot)[0]['card_id']}", wait_for="end_turn"
        )

    add_card(test, STRIKE)
    add_card(test, OUT_OF_CONTROL)
    snapshot = test.refresh()
    strike = test.find_hand_card(STRIKE, snapshot=snapshot)
    out_of_control = test.find_hand_card(OUT_OF_CONTROL, snapshot=snapshot)
    assert strike["playable"], strike
    assert not out_of_control["playable"], out_of_control
    return {
        "test71_threshold": power_amount(snapshot, POWER),
        "test71_strike_overdrive": strike["playable"],
        "test71_status_excluded": not out_of_control["playable"],
    }
