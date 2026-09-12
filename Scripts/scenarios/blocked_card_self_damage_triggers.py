"""Verify card self-damage triggers even when the damage is fully blocked."""

from __future__ import annotations


DRAW_NEXT_TURN = "DRAW_CARDS_NEXT_TURN_POWER"
STRENGTH = "STRENGTH_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
        wait_for=("play_card", "end_turn"),
    )


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST88")
    test.play_card("RD_MOD_CARD_TEST88", wait_for="end_turn")
    assert not hand(test.refresh())


def run(test):
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)

    add_card(test, "RD_MOD_CARD_TEST50")
    test.play_card("RD_MOD_CARD_TEST50", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST89")
    test.play_card("RD_MOD_CARD_TEST89", wait_for="end_turn")

    test.run_console_command("block 10 0", wait_for="end_turn")
    before = test.refresh()
    hp_before = int(combat(before)["player"]["current_hp"])
    block_before = int(combat(before)["player"]["block"])
    strength_before = power_amount(before, STRENGTH)
    draw_before = power_amount(before, DRAW_NEXT_TURN)

    add_card(test, "RD_MOD_CARD_TEST7")
    test.play_card("RD_MOD_CARD_TEST7", wait_for="end_turn")
    after = test.refresh()
    hp_after = int(combat(after)["player"]["current_hp"])
    block_after = int(combat(after)["player"]["block"])
    strength_gain = power_amount(after, STRENGTH) - strength_before
    draw_gain = power_amount(after, DRAW_NEXT_TURN) - draw_before

    assert hp_after == hp_before, (hp_before, hp_after)
    assert block_before - block_after == 2, (block_before, block_after)
    assert strength_gain == 2, strength_gain
    assert draw_gain == 2, draw_gain

    return {
        "fully_blocked_damage_events": 2,
        "hp_lost": 0,
        "block_lost": 2,
        "strength_gain": strength_gain,
        "next_turn_extra_draw": 2,
    }
