"""Runtime assertions for section 8 basic combination cards."""

from __future__ import annotations


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
SELF_DAMAGE_STRENGTH = "RD_MOD_POWER_CARD_SELF_DAMAGE_STRENGTH_POWER"
STRENGTH = "STRENGTH_POWER"
VULNERABLE = "VULNERABLE_POWER"
WEAK = "WEAK_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def player_power(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def enemy_power(snapshot, power_id, enemy_index=0):
    powers = combat(snapshot)["enemies"][enemy_index]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def pile_count(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(f"{pile}_cards", [])
    return len(cards)


def new_combat(test):
    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def upgrade_hand_card(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")

    # Test4 only draws when Preparation is present.
    test.run_console_command(f"power {PREPARATION} 1 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST4")
    draw_before = pile_count(test.refresh(), "draw")
    test.play_card("RD_MOD_CARD_TEST4", target_index=0)
    draw_after = pile_count(test.refresh(), "draw")
    assert draw_before - draw_after == 1, ("Test4 conditional draw", draw_before, draw_after)
    results["test4_conditional_draw"] = 1

    # Test5+ creates an upgraded Stunt after dealing damage.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST5")
    upgrade_hand_card(test, "RD_MOD_CARD_TEST5")
    test.play_card("RD_MOD_CARD_TEST5", target_index=0)
    stunts = [card for card in hand(test.refresh()) if card["card_id"] == "RD_MOD_CARD_STUNT"]
    assert len(stunts) == 1 and stunts[0]["upgraded"], stunts
    results["test5_generated_upgraded_stunt"] = True

    # Test6 deals three separate hits and creates OutOfControl.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST6")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST6", target_index=0)
    after = test.refresh()
    hp_after = int(combat(after)["enemies"][0]["current_hp"])
    assert hp_before - hp_after == 12, ("Test6 damage", hp_before, hp_after)
    assert any(card["card_id"] == "RD_MOD_CARD_OUT_OF_CONTROL" for card in hand(after)), hand(after)
    results["test6_damage"] = hp_before - hp_after
    results["test6_generated_out_of_control"] = True

    # Test7 self-damage is two card-sourced events, so Test50 grants Strength twice.
    new_combat(test)
    test.run_console_command(f"power {SELF_DAMAGE_STRENGTH} 1 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST7")
    before = test.refresh()
    player_hp_before = int(combat(before)["player"]["current_hp"])
    enemy_hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST7", target_index=0)
    after = test.refresh()
    assert player_hp_before - int(combat(after)["player"]["current_hp"]) == 2
    assert enemy_hp_before - int(combat(after)["enemies"][0]["current_hp"]) == 12
    assert player_power(after, STRENGTH) == 2, combat(after)["player"]["powers"]
    results["test7_self_damage_events"] = 2
    results["test7_strength_triggers"] = 2

    # Test17 applies Vulnerable before its hit, so the same hit is amplified.
    new_combat(test)
    test.run_console_command(f"power {FLIGHT} 1 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST17")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST17", target_index=0)
    after = test.refresh()
    damage = hp_before - int(combat(after)["enemies"][0]["current_hp"])
    assert enemy_power(after, VULNERABLE) == 2, combat(after)["enemies"][0]["powers"]
    assert damage > 7, ("Test17 Vulnerable was not applied before damage", damage)
    results["test17_vulnerable"] = 2
    results["test17_amplified_damage"] = damage

    # Test18 deals damage and then applies Weak when Preparation was present.
    new_combat(test)
    test.run_console_command(f"power {PREPARATION} 1 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TEST18")
    test.play_card("RD_MOD_CARD_TEST18", target_index=0)
    after = test.refresh()
    assert enemy_power(after, WEAK) == 2, combat(after)["enemies"][0]["powers"]
    results["test18_weak"] = 2

    # Test34+ creates exactly three upgraded Stunts.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST34")
    upgrade_hand_card(test, "RD_MOD_CARD_TEST34")
    test.play_card("RD_MOD_CARD_TEST34")
    stunts = [card for card in hand(test.refresh()) if card["card_id"] == "RD_MOD_CARD_STUNT"]
    assert len(stunts) == 3 and all(card["upgraded"] for card in stunts), stunts
    results["test34_generated_upgraded_stunts"] = len(stunts)

    return results
