"""Runtime assertions for fixes found during the post-update card review."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
APPLE = "RD_MOD_CARD_APPLE_CIDER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def enemy_hp(snapshot):
    return int(combat(snapshot)["enemies"][0]["current_hp"])


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
        wait_for=("play_card", "end_turn"),
    )


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST25")
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    assert not hand(test.refresh())


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(
        "upgrade " + str(card["index"]),
        wait_for="play_card",
    )
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST32")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST32")
    assert int(upgraded["energy_cost"]) == 0, upgraded
    results["test32_upgraded_cost"] = 0

    new_combat(test)
    discard_hand(test)
    test.run_console_command("power " + FLIGHT + " 4 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST31")
    test.play_card("RD_MOD_CARD_TEST31", wait_for="end_turn")
    before_enemy = test.refresh()
    protected_flight = power_amount(before_enemy, FLIGHT)
    test.refresh()
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert power_amount(next_turn, FLIGHT) == protected_flight
    results["test31_enemy_attack_preserved_flight"] = protected_flight

    new_combat(test)
    discard_hand(test)
    test.run_console_command("power " + FLIGHT + " 4 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST31")
    test.play_card("RD_MOD_CARD_TEST31", wait_for="end_turn")
    flight_to_consume = power_amount(test.refresh(), FLIGHT)
    add_card(test, "RD_MOD_CARD_TEST75")
    test.run_console_command("energy 1", wait_for="play_card")
    energy_before = int(combat(test.refresh())["player"]["energy"])
    test.play_card("RD_MOD_CARD_TEST75", wait_for="end_turn")
    after_consume = test.refresh()
    assert power_amount(after_consume, FLIGHT) == 0
    energy_after = int(combat(after_consume)["player"]["energy"])
    assert energy_after - energy_before == flight_to_consume - 1
    results["test75_consumed_protected_flight"] = flight_to_consume

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST76")
    upgrade(test, "RD_MOD_CARD_TEST76")
    test.play_card("RD_MOD_CARD_TEST76")
    after_generate = test.refresh()
    apples = [card for card in hand(after_generate) if card["card_id"] == APPLE]
    assert int(combat(after_generate)["player"]["block"]) == 8
    assert len(apples) == 2 and all(not card["upgraded"] for card in apples)
    results["test76_block"] = 8
    results["test76_apples"] = 2

    new_combat(test)
    discard_hand(test)
    add_card(test, APPLE)
    test.play_card(APPLE, wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST23")
    before_test23 = test.refresh()
    positive_layers = sum(
        max(int(power["amount"]), 0)
        for power in combat(before_test23)["player"]["powers"]
    )
    hp_before = enemy_hp(before_test23)
    test.play_card("RD_MOD_CARD_TEST23", target_index=0, wait_for="end_turn")
    dealt = hp_before - enemy_hp(test.refresh())
    strength = power_amount(before_test23, "STRENGTH_POWER")
    assert positive_layers > 0
    assert dealt == 7 + positive_layers + strength, (
        positive_layers,
        strength,
        dealt,
    )
    results["test23_temporary_positive_layers"] = positive_layers

    return results
