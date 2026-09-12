"""Runtime assertions for the 2026-09-02 card update batch."""

from __future__ import annotations

import re


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
TEMPORARY_OVERDRIVE = "RD_MOD_POWER_TEMPORARY_OVERDRIVE_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(pile + "_cards", [])
    return [card["card_id"] for card in cards]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def enemy_durabilities(snapshot):
    return [
        int(enemy["current_hp"]) + int(enemy["block"])
        for enemy in combat(snapshot)["enemies"]
    ]


def add_card(test, card_id):
    return test.run_console_command("card " + card_id, wait_for=("play_card", "end_turn"))


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command("upgrade " + str(card["index"]), wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST25")
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    assert not hand(test.refresh())


def new_combat(test, encounter="BYRDONIS_ELITE", grant_energy=True):
    test.run_console_command("fight " + encounter, wait_for="play_card", timeout_seconds=30)
    test.run_console_command("heal 999", wait_for="play_card")
    if grant_energy:
        test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test, "CULTISTS_NORMAL", grant_energy=False)
    test.run_console_command("energy 1", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST21")
    before = test.refresh()
    durability_before = enemy_durabilities(before)[0]
    test.play_card("RD_MOD_CARD_TEST21", target_index=0, wait_for="end_turn")
    after = test.refresh()
    damage = durability_before - enemy_durabilities(after)[0]
    assert damage == 16, damage
    assert power_amount(after, TEMPORARY_OVERDRIVE) == 1
    add_card(test, "RD_MOD_CARD_TEST9")
    test.play_card("RD_MOD_CARD_TEST9", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, TEMPORARY_OVERDRIVE) == 0
    results["test21"] = {"damage": 16, "skill_overdriven": True}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST36")
    card36 = test.find_hand_card("RD_MOD_CARD_TEST36")
    assert "固有" in card36["resolved_rules_text"], card36
    test.play_card("RD_MOD_CARD_TEST36", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 2
    assert int(combat(after)["player"]["block"]) == 5
    assert "RD_MOD_CARD_TEST36" in pile_ids(after, "exhaust")
    results["test36"] = {"flight": 2, "block": 5, "innate": True}

    new_combat(test, "CULTISTS_NORMAL")
    test.run_console_command("power " + PREPARATION + " 2 0", wait_for="end_turn")
    test.run_console_command("power " + FLIGHT + " 1 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST51")
    for enemy in combat(test.refresh())["enemies"]:
        test.run_console_command(
            "block 100 " + str(enemy["index"]),
            wait_for="play_card",
        )
    before = test.refresh()
    resource_layers = power_amount(before, PREPARATION) + power_amount(before, FLIGHT)
    card51 = test.find_hand_card("RD_MOD_CARD_TEST51", snapshot=before)
    damage_match = re.search(
        r"所有敌人造成(\d+)点伤害",
        card51["resolved_rules_text"],
    )
    assert damage_match is not None, card51
    expected_damage = int(damage_match.group(1))
    durability_before = enemy_durabilities(before)
    assert len(durability_before) >= 2, durability_before
    test.play_card("RD_MOD_CARD_TEST51", wait_for="end_turn")
    after = test.refresh()
    damage = [
        old - new
        for old, new in zip(durability_before, enemy_durabilities(after))
    ]
    assert damage and all(value == expected_damage for value in damage), (
        resource_layers,
        damage,
    )
    assert power_amount(after, PREPARATION) == 0
    assert power_amount(after, FLIGHT) == 0
    results["test51"] = {
        "damage_each": damage,
        "layers_consumed": resource_layers,
    }

    new_combat(test, grant_energy=False)
    add_card(test, "RD_MOD_CARD_TEST78")
    test.play_card("RD_MOD_CARD_TEST78", wait_for="end_turn")
    after = test.refresh()
    assert pile_ids(after, "discard").count("RD_MOD_CARD_TEST78") == 1
    assert "RD_MOD_CARD_TEST78" not in pile_ids(after, "exhaust")
    assert sum(card["card_id"] == "RD_MOD_CARD_APPLE_CIDER" for card in hand(after)) == 2
    results["test78"] = {"generated": 2, "exhausted": False}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST83")
    upgraded83 = upgrade(test, "RD_MOD_CARD_TEST83")
    assert int(upgraded83["energy_cost"]) == 1, upgraded83
    test.play_card("RD_MOD_CARD_TEST83", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 4
    assert "RD_MOD_CARD_TEST3" in pile_ids(after, "exhaust")
    assert "RD_MOD_CARD_TEST4" in pile_ids(after, "exhaust")
    results["test83"] = {"cost": 1, "preparation": 4}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST86")
    card86 = test.find_hand_card("RD_MOD_CARD_TEST86")
    assert not card86["requires_target"], card86
    before = test.refresh()
    durability_before = enemy_durabilities(before)
    test.play_card("RD_MOD_CARD_TEST86", wait_for="end_turn")
    total_damage = sum(
        old - new
        for old, new in zip(durability_before, enemy_durabilities(test.refresh()))
    )
    assert total_damage == 24, total_damage
    results["test86"] = {"hits": 3, "total_damage": total_damage}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST88")
    upgrade(test, "RD_MOD_CARD_TEST88")
    card88 = test.find_hand_card("RD_MOD_CARD_TEST88")
    assert not card88["requires_target"], card88
    before = test.refresh()
    durability_before = enemy_durabilities(before)
    test.play_card("RD_MOD_CARD_TEST88", wait_for="end_turn")
    after = test.refresh()
    total_damage = sum(
        old - new
        for old, new in zip(durability_before, enemy_durabilities(after))
    )
    assert total_damage == 6, total_damage
    assert "RD_MOD_CARD_TEST3" in pile_ids(after, "discard")
    assert "RD_MOD_CARD_TEST4" in pile_ids(after, "discard")
    results["test88"] = {"discarded": 2, "total_damage": total_damage}

    return results
