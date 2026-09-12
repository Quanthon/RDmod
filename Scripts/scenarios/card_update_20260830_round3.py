"""Runtime assertions for the latest nine-card design update."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(f"{pile}_cards", [])
    return [card["card_id"] for card in cards]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def new_combat(test):
    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def enemy_hp(snapshot):
    return int(combat(snapshot)["enemies"][0]["current_hp"])


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")

    add_card(test, "RD_MOD_CARD_CHARGE")
    charge = test.find_hand_card("RD_MOD_CARD_CHARGE")
    assert int(charge["energy_cost"]) == 2, charge
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_CHARGE", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 8
    assert power_amount(after, PREPARATION) == 2
    results["charge_base"] = {"damage": 8, "preparation": 2, "cost": 2}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_CHARGE")
    charge = upgrade(test, "RD_MOD_CARD_CHARGE")
    assert int(charge["energy_cost"]) == 2, charge
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_CHARGE", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 9
    assert power_amount(after, PREPARATION) == 3
    results["charge_upgraded"] = {"damage": 9, "preparation": 3, "cost": 2}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_TEST46")
    take_off = test.find_hand_card("RD_MOD_CARD_TAKE_OFF")
    assert int(take_off["energy_cost"]) == 1, take_off
    test.play_card("RD_MOD_CARD_TAKE_OFF")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 2
    assert any(card["card_id"] == "RD_MOD_CARD_TEST46" for card in hand(after))
    results["take_off"] = {"flight": 2, "discarded": 0, "cost": 1}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST29")
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST29")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 2
    assert int(combat(after)["player"]["block"]) - block_before == 2
    results["test29"] = {"flight": 2, "block": 2}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST36")
    test36 = test.find_hand_card("RD_MOD_CARD_TEST36")
    assert int(test36["energy_cost"]) == 0 and "消耗" in test36["resolved_rules_text"], test36
    test.play_card("RD_MOD_CARD_TEST36")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 1
    assert power_amount(after, PREPARATION) == 2
    assert "RD_MOD_CARD_TEST36" in pile_ids(after, "exhaust")
    results["test36_base"] = {"flight": 1, "preparation": 2, "cost": 0}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST36")
    upgrade(test, "RD_MOD_CARD_TEST36")
    test.play_card("RD_MOD_CARD_TEST36")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 2
    assert power_amount(after, PREPARATION) == 2
    results["test36_upgraded"] = {"flight": 2, "preparation": 2}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST39")
    add_card(test, "RD_MOD_CARD_TEST46")
    test.play_card("RD_MOD_CARD_TEST39", select_card_ids=["RD_MOD_CARD_TEST46"])
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 3
    assert "RD_MOD_CARD_TEST46" in pile_ids(after, "discard")
    assert not any(card["card_id"] == "RD_MOD_CARD_TEST46" for card in hand(after))
    results["test39_and_test46"] = {"flight": 3, "discarded": "Test46", "sly_triggered": False}

    return results
