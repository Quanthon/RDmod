"""Runtime assertions for Overdrive replay propagation and Test1 wording/behavior."""

from __future__ import annotations


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
TEMPORARY_OVERDRIVE = "RD_MOD_POWER_TEMPORARY_OVERDRIVE_POWER"
OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
        wait_for=("play_card", "end_turn"),
    )


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST88")
    test.play_card("RD_MOD_CARD_TEST88", wait_for="end_turn")
    assert not hand(test.refresh())


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("heal 999", wait_for="play_card")


def run(test):
    results = {}
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)

    test.run_console_command("power " + PREPARATION + " 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST1")
    test1 = test.find_hand_card("RD_MOD_CARD_TEST1")
    assert "这张牌和本回合打出的攻击牌不消耗蓄力" in test1["resolved_rules_text"], test1
    test.play_card("RD_MOD_CARD_TEST1", target_index=0, wait_for="end_turn")
    assert power_amount(test.refresh(), PREPARATION) == 3
    add_card(test, "RD_MOD_CARD_STRIKE")
    test.play_card("RD_MOD_CARD_STRIKE", target_index=0, wait_for="end_turn")
    assert power_amount(test.refresh(), PREPARATION) == 3
    results["test1"] = {"wording_complete": True, "preparation_remaining": 3}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST70")
    test.play_card("RD_MOD_CARD_TEST70", wait_for="end_turn")
    for _ in range(2):
        add_card(test, "RD_MOD_CARD_STRIKE")
        test.play_card("RD_MOD_CARD_STRIKE", target_index=0, wait_for="end_turn")
    zero_energy = test.refresh()
    assert int(combat(zero_energy)["player"]["energy"]) == 0, combat(zero_energy)["player"]

    test.run_console_command("power DUPLICATION_POWER 1 0", wait_for="end_turn")
    test.run_console_command("power " + TEMPORARY_OVERDRIVE + " 1 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST12")
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    preparation_before = power_amount(before, PREPARATION)
    flight_before = power_amount(before, FLIGHT)
    out_of_control_before = sum(card["card_id"] == OUT_OF_CONTROL for card in hand(before))
    test.play_card("RD_MOD_CARD_TEST12", wait_for="end_turn")
    after = test.refresh()
    block_gain = int(combat(after)["player"]["block"]) - block_before
    energy = int(combat(after)["player"]["energy"])
    out_of_control_gain = sum(card["card_id"] == OUT_OF_CONTROL for card in hand(after)) - out_of_control_before
    assert block_gain == 22, block_gain
    assert energy == 2, energy
    assert out_of_control_gain == 2, out_of_control_gain
    assert power_amount(after, TEMPORARY_OVERDRIVE) == 0
    assert power_amount(after, PREPARATION) - preparation_before == 2
    assert power_amount(after, FLIGHT) - flight_before == 2
    results["overdrive_replay"] = {
        "plays": 2,
        "block_gain": block_gain,
        "energy_gain": energy,
        "out_of_control_once": out_of_control_gain,
        "overdrive_uses_consumed": 1,
        "preparation_reward": 2,
        "flight_reward": 2,
    }

    return results
