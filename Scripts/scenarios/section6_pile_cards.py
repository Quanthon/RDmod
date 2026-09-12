"""Runtime assertions for section 6 hand and pile operations."""

from __future__ import annotations


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def pile_cards(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    return (view.get("combat") or {}).get(f"{pile}_cards", [])


def pile_ids(snapshot, pile):
    return [card["card_id"] for card in pile_cards(snapshot, pile)]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def set_energy(test, amount=99):
    return test.run_console_command(f"energy {amount}", wait_for="play_card")


def new_combat(test):
    return test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)


def run(test):
    results = {}
    test.enter_test_combat()

    # Test11: choose two cards to discard, then draw two.
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_TEST11")
    before = test.refresh()
    candidates = ["RD_MOD_CARD_TEST3", "RD_MOD_CARD_OUT_OF_CONTROL"]
    expected_discarded = candidates
    draw_before = len(pile_ids(before, "draw"))
    test.play_card("RD_MOD_CARD_TEST11", select_card_ids=expected_discarded)
    after = test.refresh()
    discarded = pile_ids(after, "discard")
    assert all(card_id in discarded for card_id in expected_discarded), (
        "Test11 selected discard",
        expected_discarded,
        discarded,
    )
    assert len(pile_ids(after, "draw")) == draw_before - 2
    results["test11_selected_discarded"] = expected_discarded
    results["test11_cards_drawn"] = 2

    # Test14: gain block, then discard the leftmost remaining card.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST14")
    before = test.refresh()
    leftmost = next(card["card_id"] for card in hand(before) if card["card_id"] != "RD_MOD_CARD_TEST14")
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST14")
    after = test.refresh()
    assert leftmost in pile_ids(after, "discard"), ("Test14 leftmost discard", leftmost, pile_ids(after, "discard"))
    assert int(combat(after)["player"]["block"]) - block_before == 10
    results["test14_leftmost_discarded"] = leftmost
    results["test14_block"] = 10

    # Test22: find a combat whose draw pile contains the starter zero-cost TakeOff.
    for _ in range(10):
        new_combat(test)
        if "RD_MOD_CARD_TAKE_OFF" in pile_ids(test.refresh(), "draw"):
            break
    else:
        raise AssertionError("could not place TakeOff in draw pile after 10 combats")
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST22")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    draw_before = len(pile_ids(before, "draw"))
    test.play_card("RD_MOD_CARD_TEST22", target_index=0)
    after = test.refresh()
    assert hp_before - int(combat(after)["enemies"][0]["current_hp"]) == 12
    assert "RD_MOD_CARD_TAKE_OFF" in [card["card_id"] for card in hand(after)]
    assert len(pile_ids(after, "draw")) == draw_before - 1
    results["test22_zero_cost_drawn"] = "RD_MOD_CARD_TAKE_OFF"

    # Test28: consume the relic's generic Overdrive, then prove the retrieved card has its own eligibility.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_CHARGE")
    test.play_card("RD_MOD_CARD_CHARGE", target_index=0)
    add_card(test, "RD_MOD_CARD_CHARGE")
    test.play_card("RD_MOD_CARD_CHARGE", target_index=0, wait_for="end_turn")
    test.run_console_command("energy 2", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_CHARGE")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_CHARGE"])
    assert "RD_MOD_CARD_CHARGE" in pile_ids(test.refresh(), "discard")
    add_card(test, "RD_MOD_CARD_TEST28")
    test28 = test.find_hand_card("RD_MOD_CARD_TEST28")
    test.client.play_card(int(test28["index"]))
    selecting = test.wait_for_action("select_deck_card", timeout_seconds=20, settle=True)
    option = next(
        int(card["index"])
        for card in selecting.state["selection"]["cards"]
        if card["card_id"] == "RD_MOD_CARD_CHARGE"
    )
    test.client.select_deck_card(option)
    selected = test.wait_for_action("play_card", timeout_seconds=20, settle=True)
    returned = next(
        card
        for card in hand(selected)
        if card["card_id"] == "RD_MOD_CARD_CHARGE"
        and "可以超速打出" in card["resolved_rules_text"]
    )
    assert int(combat(selected)["player"]["energy"]) == 1
    assert returned["playable"], ("Test28 temporary Overdrive", returned)
    test.client.play_card(int(returned["index"]), target_index=0)
    test.wait_for_action("end_turn", timeout_seconds=20, settle=True)
    results["test28_retrieved_card_overdrive_played"] = True

    # Test30: at zero energy, draw one card costing more than zero energy.
    new_combat(test)
    add_card(test, "RD_MOD_CARD_CHARGE")
    test.play_card("RD_MOD_CARD_CHARGE", target_index=0)
    add_card(test, "RD_MOD_CARD_TEST30")
    before = test.refresh()
    draw_before = len(pile_ids(before, "draw"))
    test.play_card("RD_MOD_CARD_TEST30")
    after = test.refresh()
    assert int(combat(after)["player"]["energy"]) == 0
    assert len(pile_ids(after, "draw")) == draw_before - 1
    results["test30_matching_cards_drawn"] = 1

    # Test32: exhaust all Status cards in hand and gain one Strength per card.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_TEST32")
    exhaust_before = pile_ids(test.refresh(), "exhaust").count("RD_MOD_CARD_OUT_OF_CONTROL")
    test.play_card("RD_MOD_CARD_TEST32")
    after = test.refresh()
    exhaust_after = pile_ids(after, "exhaust").count("RD_MOD_CARD_OUT_OF_CONTROL")
    assert exhaust_after - exhaust_before == 2
    assert power_amount(after, "STRENGTH_POWER") == 2
    results["test32_statuses_exhausted"] = 2
    results["test32_strength"] = 2

    return results
