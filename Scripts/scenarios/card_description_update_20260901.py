"""Runtime assertions for the latest description, note, and Test86 updates."""

from __future__ import annotations


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"


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


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
        wait_for=("play_card", "end_turn"),
    )


def new_combat(test, encounter="BYRDONIS_ELITE"):
    test.run_console_command(
        "fight " + encounter,
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


def enemy_hps(snapshot):
    return [int(enemy["current_hp"]) for enemy in combat(snapshot)["enemies"]]


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    discard_hand(test)
    test.run_console_command("power " + FLIGHT + " 2 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST23")
    upgrade(test, "RD_MOD_CARD_TEST23")
    before23 = test.refresh()
    positive_layers = sum(
        max(int(power["amount"]), 0)
        for power in combat(before23)["player"]["powers"]
    )
    hp_before = enemy_hps(before23)[0]
    test.play_card("RD_MOD_CARD_TEST23", target_index=0, wait_for="end_turn")
    dealt = hp_before - enemy_hps(test.refresh())[0]
    assert dealt == 11 + positive_layers, (positive_layers, dealt)
    results["test23_upgraded_damage"] = dealt

    new_combat(test)
    discard_hand(test)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, "RD_MOD_CARD_TEST56")
    test56 = test.find_hand_card("RD_MOD_CARD_TEST56")
    assert "抽0张牌，攻击2次" in test56["resolved_rules_text"], test56
    hp_before = enemy_hps(test.refresh())[0]
    test.play_card("RD_MOD_CARD_TEST56", target_index=0, wait_for="end_turn")
    dealt = hp_before - enemy_hps(test.refresh())[0]
    assert dealt == 10, dealt
    results["test56_cards_drawn"] = 0
    results["test56_damage"] = dealt

    new_combat(test)
    discard_hand(test)
    test.run_console_command("power " + PREPARATION + " 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST74")
    test74 = test.find_hand_card("RD_MOD_CARD_TEST74")
    assert "抽3张牌" in test74["resolved_rules_text"], test74
    before74 = test.refresh()
    draw_before = len(pile_ids(before74, "draw"))
    test.play_card("RD_MOD_CARD_TEST74", target_index=0, wait_for="end_turn")
    after74 = test.refresh()
    assert draw_before - len(pile_ids(after74, "draw")) == 3
    assert power_amount(after74, PREPARATION) == 2
    results["test74_cards_drawn"] = 3

    new_combat(test, "CULTISTS_NORMAL")
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST86")
    test86 = test.find_hand_card("RD_MOD_CARD_TEST86")
    assert not test86["requires_target"], test86
    assert "（攻击" not in test86["resolved_rules_text"], test86
    before86 = test.refresh()
    hp_before = enemy_hps(before86)
    test.play_card("RD_MOD_CARD_TEST86", wait_for="end_turn")
    hp_after = enemy_hps(test.refresh())
    total_damage = sum(before - after for before, after in zip(hp_before, hp_after))
    assert total_damage == 24, (hp_before, hp_after)
    results["test86_random_hits"] = 3
    results["test86_total_damage"] = total_damage

    return results
