"""Runtime assertions for section 7 cross-turn card effects."""

from __future__ import annotations


ENERGY_NEXT_TURN = "ENERGY_NEXT_TURN_POWER"
DRAW_NEXT_TURN = "DRAW_CARDS_NEXT_TURN_POWER"
TEST41_STRENGTH = "RD_MOD_POWER_TEST41_STRENGTH_POWER"
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
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def set_energy(test, amount=99):
    return test.run_console_command(f"energy {amount}", wait_for="play_card")


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    return test.run_console_command("heal 999", wait_for="play_card")


def heal(test):
    return test.run_console_command("heal 999", wait_for="play_card")


def upgrade_hand_card(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def end_turn(test):
    test.refresh()
    test.client.end_turn()
    return test.wait_for_action("play_card", timeout_seconds=30, settle=True)


def run(test):
    results = {}
    test.enter_test_combat()
    heal(test)

    # Test27+: schedule three energy and three extra draws for the next turn.
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST27")
    upgrade_hand_card(test, "RD_MOD_CARD_TEST27")
    test.play_card("RD_MOD_CARD_TEST27")
    scheduled = test.refresh()
    assert power_amount(scheduled, ENERGY_NEXT_TURN) == 3
    assert power_amount(scheduled, DRAW_NEXT_TURN) == 3
    next_turn = end_turn(test)
    assert int(combat(next_turn)["player"]["energy"]) == 6
    assert len(hand(next_turn)) == 8
    assert power_amount(next_turn, ENERGY_NEXT_TURN) == 0
    assert power_amount(next_turn, DRAW_NEXT_TURN) == 0
    results["test27_next_turn_energy"] = 3
    results["test27_next_turn_extra_draw"] = 3

    # Test37+: gain upgraded block now and schedule two extra cards next turn.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST37")
    upgrade_hand_card(test, "RD_MOD_CARD_TEST37")
    before_block = int(combat(test.refresh())["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST37")
    scheduled = test.refresh()
    assert int(combat(scheduled)["player"]["block"]) - before_block == 14
    assert power_amount(scheduled, DRAW_NEXT_TURN) == 2
    next_turn = end_turn(test)
    assert len(hand(next_turn)) == 7
    assert power_amount(next_turn, DRAW_NEXT_TURN) == 0
    results["test37_block"] = 14
    results["test37_next_turn_extra_draw"] = 2

    # Test41+: strength survives this turn end and expires at the next turn end.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST41")
    upgrade_hand_card(test, "RD_MOD_CARD_TEST41")
    test.play_card("RD_MOD_CARD_TEST41")
    applied = test.refresh()
    assert power_amount(applied, STRENGTH) == 5
    assert power_amount(applied, TEST41_STRENGTH) == 5
    next_turn = end_turn(test)
    assert power_amount(next_turn, STRENGTH) == 5
    assert power_amount(next_turn, TEST41_STRENGTH) == 5
    following_turn = end_turn(test)
    assert power_amount(following_turn, STRENGTH) == 0
    assert power_amount(following_turn, TEST41_STRENGTH) == 0
    results["test41_strength"] = 5
    results["test41_expired_after_next_turn"] = True

    # Test25+: discard the five cards present when played and draw five extra next turn.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST25")
    upgraded = upgrade_hand_card(test, "RD_MOD_CARD_TEST25")
    assert int(upgraded["energy_cost"]) == 0, upgraded
    before = test.refresh()
    discarded_count = len(hand(before)) - 1
    assert discarded_count == 5, discarded_count
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    scheduled = test.refresh()
    assert len(hand(scheduled)) == 0
    assert power_amount(scheduled, DRAW_NEXT_TURN) == discarded_count
    end_turn(test)
    next_turn = test.wait_until(
        lambda snapshot: (
            "play_card" in snapshot.action_names
            and len(hand(snapshot)) == 5 + discarded_count
            and power_amount(snapshot, DRAW_NEXT_TURN) == 0
        ),
        description="Test25 next-turn draw to finish",
        timeout_seconds=20,
        settle=True,
    )
    assert len(hand(next_turn)) == 5 + discarded_count
    assert power_amount(next_turn, DRAW_NEXT_TURN) == 0
    results["test25_upgraded_cost"] = 0
    results["test25_discarded"] = discarded_count
    results["test25_next_turn_extra_draw"] = discarded_count

    return results
