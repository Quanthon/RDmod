"""Runtime assertions for the remaining section 6 pile cards."""

from __future__ import annotations

from collections import Counter


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


def new_combat(test):
    return test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def spend_one_energy(test):
    add_card(test, "RD_MOD_CARD_DEFEND")
    test.play_card("RD_MOD_CARD_DEFEND")


def assert_exhausted(exhaust_before, exhaust_after, expected):
    delta = Counter(exhaust_after) - Counter(exhaust_before)
    assert delta == Counter(expected), ("unexpected exhausted cards", expected, delta)


def run(test):
    results = {}
    test.enter_test_combat()

    # Test33: with two energy, exhaust the two leftmost other cards and gain block twice.
    spend_one_energy(test)
    add_card(test, "RD_MOD_CARD_TEST33")
    before = test.refresh()
    expected = [
        card["card_id"]
        for card in hand(before)
        if card["card_id"] != "RD_MOD_CARD_TEST33"
    ][:2]
    exhaust_before = pile_ids(before, "exhaust")
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST33")
    after = test.refresh()
    assert_exhausted(exhaust_before, pile_ids(after, "exhaust"), expected)
    assert int(combat(after)["player"]["block"]) - block_before == 10
    assert int(combat(after)["player"]["energy"]) == 0
    results["test33_x"] = 2
    results["test33_leftmost_exhausted"] = expected
    results["test33_block"] = 10

    # Its upgrade changes each block gain from 5 to 7 without changing X behavior.
    new_combat(test)
    spend_one_energy(test)
    add_card(test, "RD_MOD_CARD_TEST33")
    test33 = test.find_hand_card("RD_MOD_CARD_TEST33")
    test.run_console_command(f"upgrade {test33['index']}", wait_for="play_card")
    upgraded = test.find_hand_card("RD_MOD_CARD_TEST33")
    assert upgraded["upgraded"], upgraded
    before = test.refresh()
    expected = [
        card["card_id"]
        for card in hand(before)
        if card["card_id"] != "RD_MOD_CARD_TEST33"
    ][:2]
    exhaust_before = pile_ids(before, "exhaust")
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST33")
    after = test.refresh()
    assert_exhausted(exhaust_before, pile_ids(after, "exhaust"), expected)
    assert int(combat(after)["player"]["block"]) - block_before == 14
    results["test33_upgraded_block"] = 14

    # Test61 moved to card_design_update.py after its full effect redesign.

    return results
