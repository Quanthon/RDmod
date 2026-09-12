"""Ensure Test23 does not count RitsuLib's temporary-power wrapper twice."""

from __future__ import annotations


CARD13 = "RD_MOD_CARD_TEST13"
CARD23 = "RD_MOD_CARD_TEST23"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
STRENGTH = "STRENGTH_POWER"
WRAPPER = "RD_MOD_POWER_TEST13_STRENGTH_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"card {CARD13}", wait_for="play_card")
    test.play_card(CARD13)
    test.run_console_command(f"power {FLIGHT} 3 0", wait_for="play_card")
    test.run_console_command(f"card {CARD23}", wait_for="play_card")

    before = test.refresh()
    powers = combat(before)["player"]["powers"]
    positive_layers = sum(
        max(int(power["amount"]), 0)
        for power in powers
        if power["power_id"] != WRAPPER
    )
    strength = next(
        (int(power["amount"]) for power in powers if power["power_id"] == STRENGTH),
        0,
    )
    enemy_hp = int(combat(before)["enemies"][0]["current_hp"])
    test.play_card(CARD23, target_index=0)
    after = test.refresh()
    damage = enemy_hp - int(combat(after)["enemies"][0]["current_hp"])
    expected = 8 + positive_layers + strength
    assert damage == expected, ("Test23 temporary wrapper", expected, damage, powers)
    return {
        "test23_positive_layers_without_wrapper": positive_layers,
        "test23_strength_modifier": strength,
        "test23_damage": damage,
    }
