"""Runtime assertions for Test81, Test82, Test68, Test20, and Test22."""

from __future__ import annotations


APPLE = "RD_MOD_CARD_APPLE_CIDER"
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


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST25")
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    assert not hand(test.refresh())


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
    discard_hand(test)

    add_card(test, "RD_MOD_CARD_TEST81")
    test81 = upgrade(test, "RD_MOD_CARD_TEST81")
    assert "保留" in test81["resolved_rules_text"], test81
    test.play_card("RD_MOD_CARD_TEST81", wait_for="end_turn")
    add_card(test, APPLE)
    draw_before = len(pile_ids(test.refresh(), "draw"))
    test.play_card(APPLE)
    after = test.refresh()
    assert len(pile_ids(after, "draw")) == draw_before - 1
    results["test81"] = {"draw_after_exhaust": 1, "upgraded_retain": True}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST82")
    test82 = upgrade(test, "RD_MOD_CARD_TEST82")
    assert "固有" in test82["resolved_rules_text"], test82
    test.play_card("RD_MOD_CARD_TEST82", wait_for="end_turn")
    add_card(test, APPLE)
    test.play_card(APPLE, wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 1
    results["test82"] = {"preparation_after_exhaust": 1, "upgraded_innate": True}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST68")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST68")
    assert int(upgraded["energy_cost"]) == 1, upgraded
    test.play_card("RD_MOD_CARD_TEST68", wait_for="end_turn")
    test.run_console_command(f"power {PREPARATION} 9 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST77")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST77", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 9
    assert power_amount(after, PREPARATION) == 9
    hp_before_trigger = enemy_hp(after)
    energy_before = int(combat(after)["player"]["energy"])
    test.run_console_command(f"power {PREPARATION} 1 0", wait_for="play_card")
    triggered = test.refresh()
    assert hp_before_trigger - enemy_hp(triggered) == 50
    assert int(combat(triggered)["player"]["energy"]) - energy_before == 5
    assert power_amount(triggered, PREPARATION) == 0
    results["test68"] = {"attack_preserved": 9, "trigger_damage": 50, "energy": 5}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST20")
    before = test.refresh()
    hp_before = [int(enemy["current_hp"]) for enemy in combat(before)["enemies"]]
    test.play_card("RD_MOD_CARD_TEST20", wait_for="end_turn")
    after = test.refresh()
    hp_after = [int(enemy["current_hp"]) for enemy in combat(after)["enemies"]]
    assert all(before_hp - after_hp == 10 for before_hp, after_hp in zip(hp_before, hp_after))
    results["test20_all_enemies"] = len(hp_after)

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST22")
    upgrade(test, "RD_MOD_CARD_TEST22")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST22", target_index=0, wait_for=("play_card", "end_turn"))
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 12
    results["test22_multi_hit"] = {"damage": 4, "hits": 3}

    return results
