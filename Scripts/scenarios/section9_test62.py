"""Runtime assertions for Test62's immediate extra turn and hand cost penalty."""

from __future__ import annotations


EXTRA_TURN_POWER = "RD_MOD_POWER_TEST62_EXTRA_TURN_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def run(test):
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command("card RD_MOD_CARD_TEST62", wait_for="play_card")
    before = test.refresh()
    hp_before = int(combat(before)["player"]["current_hp"])

    result = test.play_card("RD_MOD_CARD_TEST62", wait_for="play_card", timeout_seconds=30)
    after = result["after"]
    costs = [int(card["energy_cost"]) for card in combat(after)["hand"] if int(card["energy_cost"]) >= 0]
    assert int(combat(after)["player"]["current_hp"]) == hp_before, (hp_before, combat(after)["player"])
    assert costs and min(costs) >= 1, costs
    assert power_amount(after, EXTRA_TURN_POWER) == 0, combat(after)["player"]["powers"]

    piles = (after.state.get("agent_view") or {}).get("combat") or {}
    discard = piles.get("discard_cards", [])
    assert any(card.get("card_id") == "RD_MOD_CARD_TEST62" for card in discard), discard

    return {
        "test62_extra_turn_kept_player_hp": hp_before,
        "test62_hand_costs": costs,
        "test62_power_consumed": True,
        "test62_card_resolved": True,
    }
