"""Runtime assertions for Test89 card-self-damage next-turn draw."""

from __future__ import annotations


DRAW_NEXT_TURN = "DRAW_CARDS_NEXT_TURN_POWER"
TEST89_POWER = "RD_MOD_POWER_CARD_SELF_DAMAGE_NEXT_TURN_DRAW_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id, pile="hand"):
    suffix = "" if pile == "hand" else " " + pile
    return test.run_console_command(
        "card " + card_id + suffix,
        wait_for=("play_card", "end_turn"),
    )


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST88")
    test.play_card("RD_MOD_CARD_TEST88", wait_for="end_turn")
    assert not hand(test.refresh())


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command("upgrade " + str(card["index"]), wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def run(test):
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)

    add_card(test, "RD_MOD_CARD_TEST89")
    upgraded89 = upgrade(test, "RD_MOD_CARD_TEST89")
    assert int(upgraded89["energy_cost"]) == 1, upgraded89
    assert "固有" in upgraded89["resolved_rules_text"], upgraded89
    test.play_card("RD_MOD_CARD_TEST89", wait_for="end_turn")
    assert power_amount(test.refresh(), TEST89_POWER) == 1

    for _ in range(7):
        add_card(test, "RD_MOD_CARD_STRIKE", "draw")
    add_card(test, "RD_MOD_CARD_TEST7")
    before = test.refresh()
    hp_before = int(combat(before)["player"]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST7", wait_for="end_turn")
    after_damage = test.refresh()
    hp_loss = hp_before - int(combat(after_damage)["player"]["current_hp"])
    assert hp_loss == 2, hp_loss
    assert power_amount(after_damage, DRAW_NEXT_TURN) == 2

    test.refresh()
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert len(hand(next_turn)) == 7, hand(next_turn)
    assert power_amount(next_turn, DRAW_NEXT_TURN) == 0

    return {
        "test89_power": 1,
        "card_self_damage_events": 2,
        "next_turn_extra_draw": 2,
        "next_turn_hand": 7,
        "upgraded_innate": True,
    }
