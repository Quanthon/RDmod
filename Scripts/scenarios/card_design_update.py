"""Runtime assertions for the 28-card design update's changed mechanics."""

from __future__ import annotations


OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"
TEMP_OVERDRIVE = "RD_MOD_POWER_TEMPORARY_OVERDRIVE_POWER"
DISCARD_STATUS = "RD_MOD_POWER_DISCARDED_STATUS_EXHAUST_POWER"
LOW_HAND = "RD_MOD_POWER_LOW_HAND_OVERDRIVE_POWER"


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


def upgrade(test, card_id):
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

    # Test6 now deals 4 damage three times and creates OutOfControl.
    add_card(test, "RD_MOD_CARD_TEST6")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST6", target_index=0)
    after = test.refresh()
    damage = hp_before - int(combat(after)["enemies"][0]["current_hp"])
    assert damage == 12 and OUT_OF_CONTROL in [card["card_id"] for card in hand(after)]
    results["test6_damage"] = damage

    # Test26+ is free, Exhausts, and grants two temporary Overdrive uses.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST26")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST26")
    assert int(upgraded["energy_cost"]) == 0
    test.play_card("RD_MOD_CARD_TEST26")
    after = test.refresh()
    assert power_amount(after, TEMP_OVERDRIVE) == 2
    assert "RD_MOD_CARD_TEST26" in pile_ids(after, "exhaust")
    results["test26_temporary_overdrive"] = 2

    # Test30+ is free and draws two cards costing more than current zero energy.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST33")
    test.play_card("RD_MOD_CARD_TEST33", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST30")
    add_card(test, "RD_MOD_CARD_CHARGE", "draw")
    add_card(test, "RD_MOD_CARD_TEST3", "draw")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST30")
    assert int(upgraded["energy_cost"]) == 0
    draw_before = len(pile_ids(test.refresh(), "draw"))
    test.play_card("RD_MOD_CARD_TEST30")
    after = test.refresh()
    assert len(pile_ids(after, "draw")) == draw_before - 2
    results["test30_matching_draw"] = 2

    # Test32+ costs one, Retains, Exhausts itself, and converts two Statuses to Strength.
    new_combat(test)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, OUT_OF_CONTROL)
    add_card(test, "RD_MOD_CARD_TEST32")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST32")
    assert int(upgraded["energy_cost"]) == 1 and "保留" in upgraded["resolved_rules_text"]
    test.play_card("RD_MOD_CARD_TEST32")
    after = test.refresh()
    assert power_amount(after, "STRENGTH_POWER") == 2
    assert pile_ids(after, "exhaust").count(OUT_OF_CONTROL) >= 2
    assert "RD_MOD_CARD_TEST32" in pile_ids(after, "exhaust")
    results["test32_strength"] = 2

    # Test46 remains native Sly after changing from Power to Skill.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_TEST46")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_TEST46"])
    after = test.refresh()
    assert power_amount(after, "RD_MOD_POWER_FLIGHT_POWER") == 6
    assert "RD_MOD_CARD_TEST46" in pile_ids(after, "discard")
    results["test46_sly_flight"] = 4

    # Test48+ Exhausts a discarded Status and grants six Block.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST48")
    upgrade(test, "RD_MOD_CARD_TEST48")
    test.play_card("RD_MOD_CARD_TEST48")
    assert power_amount(test.refresh(), DISCARD_STATUS) == 6
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, OUT_OF_CONTROL)
    block_before = int(combat(test.refresh())["player"]["block"])
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=[OUT_OF_CONTROL])
    after = test.refresh()
    assert int(combat(after)["player"]["block"]) - block_before == 6
    assert OUT_OF_CONTROL in pile_ids(after, "exhaust")
    results["test48_block"] = 6

    # Test53 shows and uses the current completed-card energy total.
    new_combat(test)
    for _ in range(4):
        add_card(test, "RD_MOD_CARD_TEST3")
        test.play_card("RD_MOD_CARD_TEST3", target_index=0)
    add_card(test, "RD_MOD_CARD_TEST53")
    test53 = test.find_hand_card("RD_MOD_CARD_TEST53")
    assert "当前耗能总和：12" in test53["resolved_rules_text"], test53["resolved_rules_text"]
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    energy_before = int(combat(before)["player"]["energy"])
    test.play_card("RD_MOD_CARD_TEST53")
    after = test.refresh()
    assert hp_before - int(combat(after)["enemies"][0]["current_hp"]) == 50
    assert int(combat(after)["player"]["energy"]) - energy_before == 5
    results["test53_energy_total"] = 12

    # Test61+ deals 12 damage and stops drawing as soon as OutOfControl is drawn.
    new_combat(test)
    while pile_ids(test.refresh(), "draw"):
        snapshot = test.refresh()
        if len(hand(snapshot)) >= 10:
            test.run_console_command(
                f"remove_card {hand(snapshot)[0]['card_id']}", wait_for="play_card"
            )
        test.run_console_command("draw 1", wait_for="play_card")
    while len(hand(test.refresh())) > 8:
        snapshot = test.refresh()
        test.run_console_command(
            f"remove_card {hand(snapshot)[0]['card_id']}", wait_for="play_card"
        )
    add_card(test, OUT_OF_CONTROL, "draw")
    add_card(test, "RD_MOD_CARD_TEST61")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST61")
    assert int(upgraded["energy_cost"]) == 2
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    hand_before = len(hand(before))
    test.play_card("RD_MOD_CARD_TEST61", target_index=0)
    after = test.refresh()
    assert hp_before - int(combat(after)["enemies"][0]["current_hp"]) == 12
    assert OUT_OF_CONTROL in [card["card_id"] for card in hand(after)]
    assert len(hand(after)) == hand_before
    results["test61_damage"] = 12
    results["test61_drawn_until_status"] = True

    # Test71+ sets a three-card threshold and never grants Overdrive to Status cards.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST71")
    upgraded = upgrade(test, "RD_MOD_CARD_TEST71")
    assert int(upgraded["energy_cost"]) == 1
    test.play_card("RD_MOD_CARD_TEST71")
    assert power_amount(test.refresh(), LOW_HAND) == 3
    add_card(test, "RD_MOD_CARD_TEST33")
    test.play_card("RD_MOD_CARD_TEST33", wait_for="end_turn")
    for _ in range(4):
        add_card(test, "RD_MOD_CARD_STRIKE")
    test.play_card("RD_MOD_CARD_STRIKE", target_index=0, wait_for="end_turn")
    while hand(test.refresh()):
        snapshot = test.refresh()
        test.run_console_command(
            f"remove_card {hand(snapshot)[0]['card_id']}", wait_for="end_turn"
        )
    add_card(test, "RD_MOD_CARD_STRIKE")
    add_card(test, OUT_OF_CONTROL)
    while True:
        snapshot = test.refresh()
        removable = [
            card
            for card in hand(snapshot)
            if card["card_id"] not in {"RD_MOD_CARD_STRIKE", OUT_OF_CONTROL}
        ]
        if not removable:
            break
        test.run_console_command(f"remove_card {removable[0]['card_id']}", wait_for="play_card")
    snapshot = test.refresh()
    strike = test.find_hand_card("RD_MOD_CARD_STRIKE", snapshot=snapshot)
    out_of_control = test.find_hand_card(OUT_OF_CONTROL, snapshot=snapshot)
    assert strike["playable"], strike
    assert not out_of_control["playable"], out_of_control
    results["test71_threshold"] = 3
    results["test71_status_excluded"] = True

    return results
