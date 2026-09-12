"""Runtime assertions for section 5 card-instance state effects."""

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


def pile_lines(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    return [entry["line"] for entry in (view.get("combat") or {}).get(pile, [])]


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def set_energy(test, amount=99):
    return test.run_console_command(f"energy {amount}", wait_for="play_card")


def new_combat(test):
    return test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)


def card_costs(cards):
    return [int(card["energy_cost"]) for card in cards]


def run(test):
    results = {}
    stale = test.refresh()
    if "select_deck_card" in stale.action_names:
        test.client.select_deck_card(0)
        test.wait_for_action("play_card", timeout_seconds=20, settle=True)
    test.enter_test_combat()

    # Test8: select a specific hand card, then prove it survives the end-turn discard.
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST8")
    before = test.refresh()
    test8 = test.find_hand_card("RD_MOD_CARD_TEST8", snapshot=before)
    test.client.play_card(int(test8["index"]), target_index=0)
    selecting = test.wait_for_action("select_deck_card", timeout_seconds=20, settle=True)
    options = selecting.state["selection"]["cards"]
    option_index = next(int(card["index"]) for card in options if card["card_id"] == "RD_MOD_CARD_TEST3")
    test.client.select_deck_card(option_index)
    selected = test.wait_for_action("play_card", timeout_seconds=20, settle=True)
    assert any(card["card_id"] == "RD_MOD_CARD_TEST3" for card in hand(selected)), "Test8 selection lost Test3"
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert any(card["card_id"] == "RD_MOD_CARD_TEST3" for card in hand(next_turn)), (
        "Test8 selected card was discarded",
        [card["card_id"] for card in hand(next_turn)],
    )
    results["test8_selected_card_retained"] = True

    # Test16: only the leftmost two remaining hand cards receive a one-turn reduction.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST16")
    before = test.refresh()
    candidates = [card for card in hand(before) if card["card_id"] != "RD_MOD_CARD_TEST16"]
    old_costs = card_costs(candidates)
    test.play_card("RD_MOD_CARD_TEST16", target_index=0)
    after_cards = hand(test.refresh())
    new_costs = card_costs(after_cards)
    expected = [max(0, cost - 1) if cost >= 0 else cost for cost in old_costs[:2]] + old_costs[2:]
    assert new_costs == expected, ("Test16 leftmost discount", old_costs, new_costs, expected)
    results["test16_discounted_positions"] = 2

    # Test66: after it leaves the hand, only the two rightmost cards are reduced.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_CHARGE")
    add_card(test, "RD_MOD_CARD_TEST66")
    before = test.refresh()
    candidates = [card for card in hand(before) if card["card_id"] != "RD_MOD_CARD_TEST66"]
    old_costs = card_costs(candidates)
    test.play_card("RD_MOD_CARD_TEST66")
    new_costs = card_costs(hand(test.refresh()))
    expected = old_costs[:-2] + [max(0, cost - 1) if cost >= 0 else cost for cost in old_costs[-2:]]
    assert new_costs == expected, ("Test66 rightmost discount", old_costs, new_costs, expected)
    results["test66_discounted_positions"] = 2

    # Test59: Token-rarity generated cards are reduced, while a normal card is unchanged.
    new_combat(test)
    set_energy(test)
    add_card(test, "SOVEREIGN_BLADE")
    add_card(test, "RD_MOD_CARD_TEST3")
    generated_before = int(test.find_hand_card("SOVEREIGN_BLADE")["energy_cost"])
    normal_before = int(test.find_hand_card("RD_MOD_CARD_TEST3")["energy_cost"])
    add_card(test, "RD_MOD_CARD_TEST59")
    test.play_card("RD_MOD_CARD_TEST59")
    generated_after = int(test.find_hand_card("SOVEREIGN_BLADE")["energy_cost"])
    normal_after = int(test.find_hand_card("RD_MOD_CARD_TEST3")["energy_cost"])
    assert generated_after == max(0, generated_before - 1), (
        "Test59 generated discount",
        generated_before,
        generated_after,
    )
    assert normal_after == normal_before, ("Test59 changed normal card", normal_before, normal_after)
    results["test59_generated_cost"] = generated_after

    # Test60: a card discarded this turn keeps its reduction after the listener expires.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST60")
    test.play_card("RD_MOD_CARD_TEST60")
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_TEST3")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_TEST3"])
    discarded = test.refresh()
    assert any("Test3 [2" in line for line in pile_lines(discarded, "discard")), (
        "Test60 discarded card cost",
        pile_lines(discarded, "discard"),
    )
    assert power_amount(discarded, "RD_MOD_POWER_DISCARDED_CARD_DISCOUNT_POWER") == 1
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert power_amount(next_turn, "RD_MOD_POWER_DISCARDED_CARD_DISCOUNT_POWER") == 0
    assert any("Test3 [2" in line for line in pile_lines(next_turn, "discard")), (
        "Test60 combat discount did not persist",
        pile_lines(next_turn, "discard"),
    )
    results["test60_combat_discount_persisted"] = True

    # Test52: the played instance doubles its future damage and gains one combat cost.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST52")
    before_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST52", target_index=0)
    after = test.refresh()
    after_hp = int(combat(after)["enemies"][0]["current_hp"])
    assert before_hp - after_hp == 6, ("Test52 first damage", before_hp, after_hp)
    assert any("Test52 [2" in line and "12" in line for line in pile_lines(after, "discard")), (
        "Test52 instance growth",
        pile_lines(after, "discard"),
    )
    results["test52_next_damage"] = 12
    results["test52_next_cost"] = 2

    # Test58: card block is prevented for two turns, then works again on the third.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST58")
    test.play_card("RD_MOD_CARD_TEST58")
    applied = test.refresh()
    assert power_amount(applied, "RD_MOD_POWER_FLIGHT_POWER") == 10
    assert power_amount(applied, "NO_BLOCK_POWER") == 2
    add_card(test, "RD_MOD_CARD_DEFEND")
    test.play_card("RD_MOD_CARD_DEFEND")
    assert int(combat(test.refresh())["player"]["block"]) == 0

    test.client.end_turn()
    second_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert power_amount(second_turn, "NO_BLOCK_POWER") == 1
    set_energy(test)
    add_card(test, "RD_MOD_CARD_DEFEND")
    test.play_card("RD_MOD_CARD_DEFEND")
    assert int(combat(test.refresh())["player"]["block"]) == 0

    test.client.end_turn()
    third_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert power_amount(third_turn, "NO_BLOCK_POWER") == 0
    set_energy(test)
    add_card(test, "RD_MOD_CARD_DEFEND")
    before_block = int(combat(test.refresh())["player"]["block"])
    test.play_card("RD_MOD_CARD_DEFEND")
    after_block = int(combat(test.refresh())["player"]["block"])
    assert after_block - before_block == 5, ("Test58 block restored", before_block, after_block)
    results["test58_no_block_turns"] = 2
    results["test58_block_restored"] = after_block - before_block

    return results
