"""Runtime assertions for section 9 low-frequency cards except Test62."""

from __future__ import annotations


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
TEST68_POWER = "RD_MOD_POWER_TEST68_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(f"{pile}_cards", [])
    return [card["card_id"] for card in cards]


def all_combat_card_ids(snapshot):
    ids = [card["card_id"] for card in hand(snapshot)]
    for pile in ("draw", "discard", "exhaust"):
        ids.extend(pile_ids(snapshot, pile))
    return ids


def contains_value(value, expected):
    if isinstance(value, dict):
        return any(contains_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return value == expected


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def new_combat(test):
    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")

    # Test19 gains block from only the damage that passes through enemy block.
    test.run_console_command("block 5 1", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST19")
    before = test.refresh()
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    player_block = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST19", target_index=0)
    after = test.refresh()
    damage = enemy_hp - int(combat(after)["enemies"][0]["current_hp"])
    block = int(combat(after)["player"]["block"]) - player_block
    assert (damage, block) == (3, 3), ("Test19", damage, block)
    results["test19_unblocked_damage"] = damage
    results["test19_block"] = block

    # Test54 deals four hits and creates a same-upgrade-state copy in hand.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST54")
    before = test.refresh()
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST54", target_index=0)
    after = test.refresh()
    copies = [card for card in hand(after) if card["card_id"] == "RD_MOD_CARD_TEST54"]
    assert enemy_hp - int(combat(after)["enemies"][0]["current_hp"]) == 8
    assert len(copies) == 1 and not copies[0]["upgraded"], copies
    results["test54_damage"] = 8
    results["test54_copies"] = 1

    # Test55 only grants Entropic Brew when its own hit is fatal.
    new_combat(test)
    before = test.refresh()
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    test.run_console_command(f"damage {enemy_hp - 1} 1", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST55")
    test.play_card("RD_MOD_CARD_TEST55", target_index=0)
    after = test.refresh()
    assert contains_value(after.state, "ENTROPIC_BREW"), after.state.get("run")
    results["test55_entropic_brew"] = True

    # Test56 counts every OutOfControl already in hand after its matching draw step.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_TEST56")
    before = test.refresh()
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST56", target_index=0)
    after = test.refresh()
    damage = enemy_hp - int(combat(after)["enemies"][0]["current_hp"])
    assert damage == 12, ("Test56", damage, hand(before))
    results["test56_damage_for_two_out_of_control"] = damage

    # Test64 raises only the lower of Preparation and Flight.
    new_combat(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="play_card")
    test.run_console_command(f"power {FLIGHT} 7 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST64")
    test.play_card("RD_MOD_CARD_TEST64")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 7
    assert power_amount(after, FLIGHT) == 7
    results["test64_equalized"] = 7

    # Test65 transforms Status cards in combat piles into Stunts.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_OUT_OF_CONTROL"])
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_TEST65")
    before_stunts = all_combat_card_ids(test.refresh()).count("RD_MOD_CARD_STUNT")
    test.play_card("RD_MOD_CARD_TEST65")
    after = test.refresh()
    ids = all_combat_card_ids(after)
    assert "RD_MOD_CARD_OUT_OF_CONTROL" not in ids, ids
    assert ids.count("RD_MOD_CARD_STUNT") - before_stunts == 2, ids
    results["test65_transformed_statuses"] = 2

    # Test68 stores 50 damage, then one batch consumption of 10 Preparation triggers once.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST68")
    test.play_card("RD_MOD_CARD_TEST68")
    applied = test.refresh()
    assert power_amount(applied, TEST68_POWER) == 50
    test.run_console_command(f"power {PREPARATION} 10 0", wait_for="play_card")
    before = test.refresh()
    hp_before = [int(enemy["current_hp"]) for enemy in combat(before)["enemies"]]
    energy_before = int(combat(before)["player"]["energy"])
    test.run_console_command(f"power {PREPARATION} -10 0", wait_for="play_card")
    after = test.refresh()
    hp_after = [int(enemy["current_hp"]) for enemy in combat(after)["enemies"]]
    assert all(start - end == 50 for start, end in zip(hp_before, hp_after)), (hp_before, hp_after)
    assert int(combat(after)["player"]["energy"]) - energy_before == 5
    results["test68_aoe"] = 50
    results["test68_energy"] = 5

    return results
