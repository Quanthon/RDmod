"""Runtime assertions for AppleCider and Test76 through Test80."""

from __future__ import annotations


APPLE = "RD_MOD_CARD_APPLE_CIDER"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"
STRENGTH = "STRENGTH_POWER"


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


def add_card(test, card_id, pile="hand"):
    suffix = "" if pile == "hand" else f" {pile}"
    return test.run_console_command(f"card {card_id}{suffix}", wait_for="play_card")


def new_combat(test):
    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def new_combat_with_base_energy(test):
    test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)
    return test.run_console_command("heal 999", wait_for="play_card")


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


def apple_cards(snapshot):
    return [card for card in hand(snapshot) if card["card_id"] == APPLE]


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)

    add_card(test, APPLE)
    test.play_card(APPLE, wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, STRENGTH) == 2
    assert APPLE in pile_ids(after, "exhaust")
    results["apple_cider"] = {"strength": 2, "exhausted": True}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST76")
    upgrade(test, "RD_MOD_CARD_TEST76")
    test.play_card("RD_MOD_CARD_TEST76")
    generated = apple_cards(test.refresh())
    assert len(generated) == 2 and all(not card["upgraded"] for card in generated), generated
    assert int(combat(test.refresh())["player"]["block"]) == 8
    results["test76"] = {"block": 8, "apple_cider": 2}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST77")
    upgrade(test, "RD_MOD_CARD_TEST77")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST77", target_index=0)
    after = test.refresh()
    generated = apple_cards(after)
    assert hp_before - enemy_hp(after) == 7
    assert len(generated) == 1 and not generated[0]["upgraded"], generated
    results["test77"] = {"damage": 7, "apple_cider": 1}

    new_combat_with_base_energy(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST78")
    upgrade(test, "RD_MOD_CARD_TEST78")
    expected_x = int(combat(test.refresh())["player"]["energy"])
    test.play_card("RD_MOD_CARD_TEST78")
    generated = apple_cards(test.refresh())
    assert len(generated) == expected_x + 1 and all(not card["upgraded"] for card in generated), generated
    results["test78"] = {"x": expected_x, "apple_cider": expected_x + 1}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST79")
    upgrade(test, "RD_MOD_CARD_TEST79")
    test.play_card("RD_MOD_CARD_TEST79")
    generated = apple_cards(test.refresh())
    assert len(generated) == 2 and all(card["upgraded"] for card in generated), generated
    assert all("保留" in card["resolved_rules_text"] for card in generated), generated
    add_card(test, APPLE)
    later = apple_cards(test.refresh())
    assert len(later) == 3 and all("保留" in card["resolved_rules_text"] for card in later), later
    results["test79"] = {"initial": 2, "later_retained": True}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST80")
    upgrade(test, "RD_MOD_CARD_TEST80")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST80", wait_for="end_turn")
    after = test.refresh()
    apples = apple_cards(after)
    assert hp_before - enemy_hp(after) == 14
    assert len(hand(after)) == 10
    assert [card["card_id"] for card in hand(after)].count(OUT_OF_CONTROL) == 2
    assert len(apples) == 8 and all(not card["upgraded"] for card in apples), apples
    results["test80"] = {"damage": 14, "out_of_control": 2, "apple_cider": 8}

    return results





