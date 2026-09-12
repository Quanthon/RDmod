"""Runtime assertions for the four-card design update."""

from __future__ import annotations


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

    add_card(test, "RD_MOD_CARD_TEST16")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST16", target_index=0)
    after = test.refresh()
    actual_damage = hp_before - enemy_hp(after)
    assert actual_damage == 3, ("Test16 damage", 3, actual_damage, hp_before, enemy_hp(after))
    results["test16_damage"] = 3

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST54")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST54", target_index=0)
    after = test.refresh()
    copies = [card for card in hand(after) if card["card_id"] == "RD_MOD_CARD_TEST54"]
    actual_damage = hp_before - enemy_hp(after)
    assert actual_damage == 6, ("Test54 base damage", 6, actual_damage, hp_before, enemy_hp(after))
    assert len(copies) == 1 and not copies[0]["upgraded"], copies
    results["test54_base_damage"] = 6

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST54")
    upgrade(test, "RD_MOD_CARD_TEST54")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST54", target_index=0)
    after = test.refresh()
    copies = [card for card in hand(after) if card["card_id"] == "RD_MOD_CARD_TEST54"]
    actual_damage = hp_before - enemy_hp(after)
    assert actual_damage == 9, ("Test54 upgraded damage", 9, actual_damage, hp_before, enemy_hp(after))
    assert len(copies) == 1 and copies[0]["upgraded"], copies
    results["test54_upgraded_damage"] = 9

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_TEST46")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_TEST46"])
    after = test.refresh()
    assert power_amount(after, "RD_MOD_POWER_FLIGHT_POWER") == 6
    assert not any(card["card_id"] == "RD_MOD_CARD_TEST46" for card in hand(after))
    results["test46_sly_power_flight"] = 4

    return results



