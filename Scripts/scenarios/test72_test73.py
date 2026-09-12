"""Runtime assertions for Test72 and Test73."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


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

    add_card(test, "RD_MOD_CARD_TEST72")
    test72 = test.find_hand_card("RD_MOD_CARD_TEST72")
    assert int(test72["energy_cost"]) == 1, test72
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST72", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 8
    assert power_amount(after, FLIGHT) == 1
    results["test72_base"] = {"damage": 8, "flight": 1, "cost": 1}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST72")
    upgrade(test, "RD_MOD_CARD_TEST72")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST72", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 9
    assert power_amount(after, FLIGHT) == 2
    results["test72_upgraded"] = {"damage": 9, "flight": 2}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST73")
    test73 = test.find_hand_card("RD_MOD_CARD_TEST73")
    assert int(test73["energy_cost"]) == 1, test73
    draw_before = len(pile_ids(test.refresh(), "draw"))
    test.play_card("RD_MOD_CARD_TEST73")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 2
    assert len(pile_ids(after, "draw")) == draw_before - 2
    results["test73_base"] = {"preparation": 2, "draw": 2, "cost": 1}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST73")
    upgrade(test, "RD_MOD_CARD_TEST73")
    draw_before = len(pile_ids(test.refresh(), "draw"))
    test.play_card("RD_MOD_CARD_TEST73")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 3
    assert len(pile_ids(after, "draw")) == draw_before - 2
    results["test73_upgraded"] = {"preparation": 3, "draw": 2}

    return results
