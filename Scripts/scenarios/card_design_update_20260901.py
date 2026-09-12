"""Runtime assertions for the September 1 workbook mechanism updates."""

from __future__ import annotations

from collections import Counter


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
TEMP_OVERDRIVE = "RD_MOD_POWER_TEMPORARY_OVERDRIVE_POWER"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def pile_entries(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    return (view.get("combat") or {}).get(f"{pile}_cards", [])


def pile_ids(snapshot, pile):
    return [card["card_id"] for card in pile_entries(snapshot, pile)]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id, pile="hand"):
    suffix = "" if pile == "hand" else f" {pile}"
    return test.run_console_command(
        f"card {card_id}{suffix}",
        wait_for=("play_card", "end_turn"),
    )


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

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST1")
    test.play_card("RD_MOD_CARD_TEST1", target_index=0, wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 3
    results["test1_preserves_own_preparation"] = 3

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST35")
    before = Counter(pile_ids(test.refresh(), "discard"))
    test.play_card("RD_MOD_CARD_TEST35", wait_for="end_turn")
    after = test.refresh()
    discarded = Counter(pile_ids(after, "discard"))
    assert discarded["RD_MOD_CARD_TEST3"] == before["RD_MOD_CARD_TEST3"] + 1
    assert discarded["RD_MOD_CARD_TEST4"] == before["RD_MOD_CARD_TEST4"] + 1
    assert power_amount(after, TEMP_OVERDRIVE) == 1
    results["test35_selected_discards"] = 2

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST52")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST52", target_index=0, wait_for="end_turn")
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 10
    discard_lines = (after.state.get("agent_view") or {})["combat"]["discard"]
    test52_line = next(
        entry["line"] for entry in discard_lines
        if entry["line"].startswith("Test52 ")
    )
    assert "[2" in test52_line and "4" in test52_line, test52_line
    results["test52_first_damage"] = 10
    results["test52_next_hits"] = 4

    new_combat(test)
    discard_hand(test)
    add_card(test, OUT_OF_CONTROL, "draw")
    add_card(test, OUT_OF_CONTROL, "discard")
    add_card(test, "RD_MOD_CARD_TEST56")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST56", target_index=0, wait_for="end_turn")
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 8
    assert [card["card_id"] for card in hand(after)].count(OUT_OF_CONTROL) == 2
    results["test56_statuses_moved"] = 2
    results["test56_damage"] = 8

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST54")
    test.play_card("RD_MOD_CARD_TEST54", target_index=0)
    generated_before = int(test.find_hand_card("RD_MOD_CARD_TEST54")["energy_cost"])
    add_card(test, "RD_MOD_CARD_TEST3")
    normal_before = int(test.find_hand_card("RD_MOD_CARD_TEST3")["energy_cost"])
    add_card(test, "RD_MOD_CARD_TEST59")
    test.play_card("RD_MOD_CARD_TEST59")
    generated_after = int(test.find_hand_card("RD_MOD_CARD_TEST54")["energy_cost"])
    normal_after = int(test.find_hand_card("RD_MOD_CARD_TEST3")["energy_cost"])
    assert generated_after == generated_before - 1
    assert normal_after == normal_before
    results["test59_generated_discount"] = generated_after

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST74")
    before = test.refresh()
    draw_before = len(pile_ids(before, "draw"))
    test.play_card("RD_MOD_CARD_TEST74", target_index=0, wait_for="end_turn")
    after = test.refresh()
    remaining_preparation = power_amount(after, PREPARATION)
    drawn = draw_before - len(pile_ids(after, "draw"))
    assert remaining_preparation == 2
    assert drawn == 3
    results["test74_remaining_preparation"] = remaining_preparation
    results["test74_drawn"] = drawn

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST8")
    upgrade(test, "RD_MOD_CARD_TEST8")
    test.play_card("RD_MOD_CARD_TEST8", target_index=0)
    selected = test.find_hand_card("RD_MOD_CARD_TEST3")
    assert "保留" in selected["resolved_rules_text"], selected
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert any(card["card_id"] == "RD_MOD_CARD_TEST3" for card in hand(next_turn))
    results["test8_permanent_retain"] = True

    return results
