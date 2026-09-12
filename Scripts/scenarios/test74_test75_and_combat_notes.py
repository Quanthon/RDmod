"""Runtime assertions for Test74, Test75, and combat-only card notes."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
STRENGTH = "STRENGTH_POWER"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"


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

    add_card(test, "RD_MOD_CARD_TEST25")
    add_card(test, "RD_MOD_CARD_STRIKE")
    add_card(test, "RD_MOD_CARD_DEFEND")
    add_card(test, "RD_MOD_CARD_CHARGE")
    expected_discard = 3
    power_before = power_amount(test.refresh(), "DRAW_CARDS_NEXT_TURN_POWER")
    test25 = test.find_hand_card("RD_MOD_CARD_TEST25")
    assert f"（额外抽{expected_discard}张牌）" in test25["resolved_rules_text"], test25["resolved_rules_text"]
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, "DRAW_CARDS_NEXT_TURN_POWER") - power_before == expected_discard
    results["test25_note"] = expected_discard

    new_combat(test)
    discard_hand(test)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, "RD_MOD_CARD_TEST32")
    test32 = test.find_hand_card("RD_MOD_CARD_TEST32")
    assert "（获得2点力量）" in test32["resolved_rules_text"], test32["resolved_rules_text"]
    test.play_card("RD_MOD_CARD_TEST32", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, STRENGTH) == 2
    results["test32_note"] = 2

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST32")
    upgraded32 = upgrade(test, "RD_MOD_CARD_TEST32")
    assert int(upgraded32["energy_cost"]) == 0, upgraded32
    assert "保留" in upgraded32["resolved_rules_text"], upgraded32
    results["test32_upgrade"] = {"energy": 0, "retain": True}
    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST53")
    test53 = test.find_hand_card("RD_MOD_CARD_TEST53")
    assert "（当前耗能总和：1）" in test53["resolved_rules_text"], test53["resolved_rules_text"]
    results["test53_note"] = 1

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST56")
    add_card(test, OUT_OF_CONTROL, "draw")
    add_card(test, OUT_OF_CONTROL, "draw")
    test56 = test.find_hand_card("RD_MOD_CARD_TEST56")
    assert "攻击2次" in test56["resolved_rules_text"], test56["resolved_rules_text"]
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST56", target_index=0, wait_for="end_turn")
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 10
    results["test56_note"] = 2

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST74")
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    hand_before = len(hand(before))
    test.play_card("RD_MOD_CARD_TEST74", wait_for="end_turn")
    after = test.refresh()
    assert int(combat(after)["player"]["block"]) == block_before
    assert len(hand(after)) == hand_before - 1
    assert power_amount(after, PREPARATION) == 0
    results["test74_without_preparation"] = {"block": 0, "draw": 0}

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST74")
    upgraded74 = upgrade(test, "RD_MOD_CARD_TEST74")
    assert "（重复3次）" in upgraded74["resolved_rules_text"], upgraded74
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST74", wait_for="end_turn")
    after = test.refresh()
    block_gained = int(combat(after)["player"]["block"]) - block_before
    assert block_gained == 12, block_gained
    assert len(hand(after)) == 6, hand(after)
    assert power_amount(after, PREPARATION) == 0
    results["test74_full_loop"] = {
        "block": block_gained,
        "draw": 6,
        "preparation": 0,
    }

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST74")
    for _ in range(9):
        add_card(test, "RD_MOD_CARD_STRIKE")
    test74 = test.find_hand_card("RD_MOD_CARD_TEST74")
    assert "（重复1次）" in test74["resolved_rules_text"], test74
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST74", wait_for="end_turn")
    after = test.refresh()
    block_gained = int(combat(after)["player"]["block"]) - block_before
    assert block_gained == 2, block_gained
    assert len(hand(after)) == 10, hand(after)
    assert power_amount(after, PREPARATION) == 2
    results["test74_stops_at_full_hand"] = {
        "block": block_gained,
        "hand": 10,
        "preparation": 2,
    }
    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {FLIGHT} 4 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST75")
    test.run_console_command("energy 1", wait_for="play_card")
    energy_before = int(combat(test.refresh())["player"]['energy'])
    test.play_card("RD_MOD_CARD_TEST75", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, FLIGHT) == 0
    assert int(combat(after)["player"]["energy"]) - energy_before == 4
    assert "RD_MOD_CARD_TEST75" in pile_ids(after, "exhaust")
    results["test75"] = {"flight_consumed": 4, "net_energy": 4}

    return results







