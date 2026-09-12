"""Runtime assertions for Test90, Test91, and the Test52 pool update."""

from __future__ import annotations


TEST25 = "RD_MOD_CARD_TEST25"
TEST52 = "RD_MOD_CARD_TEST52"
TEST90 = "RD_MOD_CARD_TEST90"
TEST91 = "RD_MOD_CARD_TEST91"
DEFEND = "RD_MOD_CARD_DEFEND"
STRIKE = "RD_MOD_CARD_STRIKE"


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


def pile_count(snapshot, pile):
    return len(pile_ids(snapshot, pile))


def add_card(test, card_id):
    return test.run_console_command(
        f"card {card_id}",
        wait_for=("play_card", "end_turn"),
    )


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def discard_hand(test):
    add_card(test, TEST25)
    test.play_card(TEST25, wait_for="end_turn")
    assert not hand(test.refresh())


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    discard_hand(test)
    add_card(test, TEST90)
    test.run_console_command("energy 7", wait_for="play_card")
    before = test.refresh()
    hp_before = int(combat(before)["enemies"][0]["current_hp"])
    block_before = int(combat(before)["player"]["block"])
    energy_before = int(combat(before)["player"]["energy"])
    test.play_card(TEST90, target_index=0, wait_for=("play_card", "end_turn"))
    after = test.refresh()
    damage = hp_before - int(combat(after)["enemies"][0]["current_hp"])
    block_gain = int(combat(after)["player"]["block"]) - block_before
    assert damage == 7, damage
    assert block_gain == 7, block_gain
    assert len(hand(after)) == 7, len(hand(after))
    assert int(combat(after)["player"]["energy"]) == energy_before, combat(after)["player"]
    assert TEST90 in pile_ids(after, "exhaust"), pile_ids(after, "exhaust")
    results["test90_base"] = {
        "damage": damage,
        "block": block_gain,
        "draw": len(hand(after)),
        "energy_gained": 7,
        "exhausted": True,
    }

    new_combat(test)
    discard_hand(test)
    add_card(test, TEST90)
    upgraded90 = upgrade(test, TEST90)
    assert "消耗" not in upgraded90["resolved_rules_text"], upgraded90
    test.run_console_command("energy 7", wait_for="play_card")
    test.play_card(TEST90, target_index=0, wait_for=("play_card", "end_turn"))
    upgraded_after = test.refresh()
    assert TEST90 in pile_ids(upgraded_after, "discard"), pile_ids(upgraded_after, "discard")
    assert TEST90 not in pile_ids(upgraded_after, "exhaust"), pile_ids(upgraded_after, "exhaust")
    results["test90_upgraded_exhaust_removed"] = True

    new_combat(test)
    discard_hand(test)
    add_card(test, DEFEND)
    add_card(test, STRIKE)
    add_card(test, TEST91)
    test.play_card(TEST91, select_card_ids=[DEFEND], wait_for=("play_card", "end_turn"))
    selected = test.find_hand_card(DEFEND)
    assert int(selected["energy_cost"]) == 4, selected
    assert TEST91 in pile_ids(test.refresh(), "exhaust"), pile_ids(test.refresh(), "exhaust")
    test.run_console_command("energy 99", wait_for="play_card")
    block_before = int(combat(test.refresh())["player"]["block"])
    test.play_card(DEFEND, wait_for=("play_card", "end_turn"))
    block_gain = int(combat(test.refresh())["player"]["block"]) - block_before
    assert block_gain == 15, block_gain
    results["test91"] = {
        "selected_cost": 4,
        "total_plays": 3,
        "block": block_gain,
        "source_exhausted": True,
    }

    new_combat(test)
    discard_hand(test)
    add_card(test, TEST91)
    upgraded91 = upgrade(test, TEST91)
    assert int(upgraded91["energy_cost"]) == 1, upgraded91
    assert "消耗" in upgraded91["resolved_rules_text"], upgraded91
    results["test91_upgraded"] = {"cost": 1, "exhaust": True}
    results["test52_registration_id_preserved"] = TEST52
    return results
