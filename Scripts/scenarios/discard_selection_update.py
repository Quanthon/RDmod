"""Runtime assertions for selectable discard card updates."""

from __future__ import annotations

from collections import Counter


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
STRENGTH = "STRENGTH_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


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


def discard_delta(before, after, card_id):
    old = Counter(pile_ids(before, "discard"))
    new = Counter(pile_ids(after, "discard"))
    return new[card_id] - old[card_id]


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")

    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    before = test.refresh()
    test.play_card(
        "RD_MOD_CARD_TAKE_OFF",
        select_card_ids=["RD_MOD_CARD_TEST3"],
    )
    after = test.refresh()
    assert power_amount(after, FLIGHT) == power_amount(before, FLIGHT) + 2
    assert discard_delta(before, after, "RD_MOD_CARD_TEST3") == 1
    results["take_off_selected_discard"] = "RD_MOD_CARD_TEST3"

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST11")
    before = test.refresh()
    test.play_card(
        "RD_MOD_CARD_TEST11",
        select_card_ids=["RD_MOD_CARD_TEST3", "RD_MOD_CARD_TEST4"],
    )
    after = test.refresh()
    assert discard_delta(before, after, "RD_MOD_CARD_TEST3") == 1
    assert discard_delta(before, after, "RD_MOD_CARD_TEST4") == 1
    results["test11_selected_discards"] = 2

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST13")
    before = test.refresh()
    test.play_card(
        "RD_MOD_CARD_TEST13",
        select_card_ids=["RD_MOD_CARD_TEST3"],
    )
    after = test.refresh()
    assert power_amount(after, STRENGTH) == 3
    assert discard_delta(before, after, "RD_MOD_CARD_TEST3") == 1
    results["test13_selected_discard"] = "RD_MOD_CARD_TEST3"

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST2")
    before = test.refresh()
    hp_before = [int(enemy["current_hp"]) for enemy in combat(before)["enemies"]]
    test.play_card(
        "RD_MOD_CARD_TEST2",
        select_card_ids=["RD_MOD_CARD_TEST3", "RD_MOD_CARD_TEST4"],
    )
    after = test.refresh()
    hp_after = [int(enemy["current_hp"]) for enemy in combat(after)["enemies"]]
    assert all(old > new for old, new in zip(hp_before, hp_after))
    assert discard_delta(before, after, "RD_MOD_CARD_TEST3") == 1
    assert discard_delta(before, after, "RD_MOD_CARD_TEST4") == 1
    results["test2_selected_discards"] = 2

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST48")
    source = test.find_hand_card("RD_MOD_CARD_TEST48")
    test.run_console_command(f"upgrade {source['index']}", wait_for="play_card")
    test.play_card("RD_MOD_CARD_TEST48")
    assert power_amount(
        test.refresh(),
        "RD_MOD_POWER_DISCARDED_STATUS_EXHAUST_POWER",
    ) == 6
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card(
        "RD_MOD_CARD_TAKE_OFF",
        select_card_ids=["RD_MOD_CARD_OUT_OF_CONTROL"],
    )
    after = test.refresh()
    assert int(combat(after)["player"]["block"]) - block_before == 6
    assert "RD_MOD_CARD_OUT_OF_CONTROL" in pile_ids(after, "exhaust")
    results["test48_upgraded_block"] = 6

    return results
