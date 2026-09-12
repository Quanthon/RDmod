"""Runtime assertions for the final eight workbook cards."""

from __future__ import annotations

from collections import Counter


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
STRENGTH = "STRENGTH_POWER"
TEMP_OVERDRIVE = "RD_MOD_POWER_TEMPORARY_OVERDRIVE_POWER"


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


def enemy_hps(snapshot):
    return [int(enemy["current_hp"]) for enemy in combat(snapshot)["enemies"]]


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")

    # Test2 damages every enemy and lets the player choose two cards to discard.
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST2")
    before = test.refresh()
    hp_before = enemy_hps(before)
    discard_before = Counter(pile_ids(before, "discard"))
    test.play_card("RD_MOD_CARD_TEST2", select_card_ids=["RD_MOD_CARD_TEST3", "RD_MOD_CARD_TEST4"])
    after = test.refresh()
    damage = [old - new for old, new in zip(hp_before, enemy_hps(after))]
    discard_after = Counter(pile_ids(after, "discard"))
    assert damage and all(value == 8 for value in damage), ("Test2 all-enemy damage", damage)
    assert discard_after["RD_MOD_CARD_TEST3"] == discard_before["RD_MOD_CARD_TEST3"] + 1
    assert discard_after["RD_MOD_CARD_TEST4"] == discard_before["RD_MOD_CARD_TEST4"] + 1
    results["test2_all_enemy_damage"] = damage
    results["test2_selected_discard"] = 2

    # Test13 gains temporary Strength before letting the player choose one discard.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST13")
    test.play_card("RD_MOD_CARD_TEST13", select_card_ids=["RD_MOD_CARD_TEST3"])
    after = test.refresh()
    assert power_amount(after, STRENGTH) == 3
    assert "RD_MOD_CARD_TEST3" in pile_ids(after, "discard")
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert power_amount(next_turn, STRENGTH) == 0
    results["test13_temporary_strength"] = 3
    results["test13_selected_discard"] = True

    # Test23 adds one damage for every positive power layer currently owned.
    new_combat(test)
    test.run_console_command(f"power {FLIGHT} 3 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST23")
    before = test.refresh()
    positive_layers = sum(
        max(int(power["amount"]), 0)
        for power in combat(before)["player"]["powers"]
    )
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST23", target_index=0)
    after = test.refresh()
    dealt = hp_before - int(combat(after)["enemies"][0]["current_hp"])
    assert dealt == 8 + positive_layers, ("Test23 positive layers", positive_layers, dealt)
    results["test23_positive_layers"] = positive_layers
    results["test23_damage"] = dealt

    # Test29 retains Skills already in hand and Skills added later this turn.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST29")
    test.play_card("RD_MOD_CARD_TEST29")
    assert power_amount(test.refresh(), FLIGHT) == 3
    add_card(test, "RD_MOD_CARD_TEST10")
    add_card(test, "RD_MOD_CARD_TEST3")
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    next_ids = [card["card_id"] for card in hand(next_turn)]
    assert "RD_MOD_CARD_TEST10" in next_ids and "RD_MOD_CARD_TEST3" not in next_ids, next_ids
    results["test29_future_skill_retained"] = True

    # Test35 discards both hand edges, grants one temporary Overdrive, and gains Retain on upgrade.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST35")
    source = test.find_hand_card("RD_MOD_CARD_TEST35")
    test.run_console_command(f"upgrade {source['index']}", wait_for="play_card")
    upgraded = test.find_hand_card("RD_MOD_CARD_TEST35")
    assert "保留" in upgraded["resolved_rules_text"], upgraded
    before = test.refresh()
    remaining = [card["card_id"] for card in hand(before) if card["card_id"] != "RD_MOD_CARD_TEST35"]
    assert remaining
    expected = Counter([remaining[0]] + ([remaining[-1]] if len(remaining) > 1 else []))
    discard_before = Counter(pile_ids(before, "discard"))
    test.play_card("RD_MOD_CARD_TEST35")
    after = test.refresh()
    discard_after = Counter(pile_ids(after, "discard"))
    for card_id, count in expected.items():
        assert discard_after[card_id] == discard_before[card_id] + count
    assert power_amount(after, TEMP_OVERDRIVE) == 1
    results["test35_edge_discards"] = sum(expected.values())
    results["test35_temporary_overdrive"] = 1
    results["test35_upgraded_retain"] = True

    # Test38 retains Attacks already in hand and Attacks added later this turn.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST38")
    test.play_card("RD_MOD_CARD_TEST38")
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST10")
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    next_ids = [card["card_id"] for card in hand(next_turn)]
    assert "RD_MOD_CARD_TEST3" in next_ids and "RD_MOD_CARD_TEST10" not in next_ids, next_ids
    assert power_amount(next_turn, PREPARATION) == 2
    results["test38_future_attack_retained"] = True

    # Test46 is a native Sly Skill: Take Off discards and auto-plays it.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_TEST46")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_TEST46"])
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 6, combat(after)["player"]["powers"]
    assert not any(card["card_id"] == "RD_MOD_CARD_TEST46" for card in hand(after))
    results["test46_sly_power_flight"] = 4

    # Test51+ consumes all Preparation and Flight, then uses the actual consumed count.
    new_combat(test)
    test.run_console_command(f"power {PREPARATION} 2 0", wait_for="play_card")
    test.run_console_command(f"power {FLIGHT} 3 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST51")
    source = test.find_hand_card("RD_MOD_CARD_TEST51")
    test.run_console_command(f"upgrade {source['index']}", wait_for="play_card")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST51", target_index=0)
    after = test.refresh()
    dealt = hp_before - int(combat(after)["enemies"][0]["current_hp"])
    assert dealt == 72, ("Test51 upgraded damage with Preparation", dealt)
    assert power_amount(after, PREPARATION) == 0 and power_amount(after, FLIGHT) == 0
    results["test51_consumed_layers"] = 5
    results["test51_upgraded_damage"] = dealt

    return results
