"""Runtime assertions for stacking multiple Test68 power instances."""

from __future__ import annotations


CARD_ID = "RD_MOD_CARD_TEST68"
POWER_ID = "RD_MOD_POWER_TEST68_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"card {CARD_ID}", wait_for="play_card")
    test.play_card(CARD_ID)
    test.run_console_command(f"card {CARD_ID}", wait_for="play_card")
    test.play_card(CARD_ID)

    test.run_console_command("block 100 1", wait_for="play_card")
    before = test.refresh()
    instances = [
        power
        for power in combat(before)["player"]["powers"]
        if power["power_id"] == POWER_ID
    ]
    assert len(instances) == 1, ("Test68 instances", instances)
    assert int(instances[0]["amount"]) == 2, ("Test68 stacks", instances)
    energy_before = int(combat(before)["player"]["energy"])
    enemy_states = [
        (int(enemy["current_hp"]), int(enemy["block"]))
        for enemy in combat(before)["enemies"]
    ]

    test.run_console_command(f"power {PREPARATION} 10 0", wait_for="play_card")
    test.run_console_command(f"power {PREPARATION} -10 0", wait_for="play_card")
    after = test.refresh()
    damages = [
        old_hp - int(enemy["current_hp"]) + old_block - int(enemy["block"])
        for (old_hp, old_block), enemy in zip(enemy_states, combat(after)["enemies"])
    ]
    energy_gain = int(combat(after)["player"]["energy"]) - energy_before
    assert damages and all(damage == 100 for damage in damages), damages
    assert energy_gain == 10, ("Test68 stacked energy", energy_gain)
    return {
        "test68_instances": len(instances),
        "test68_stacks": int(instances[0]["amount"]),
        "test68_damage": damages,
        "test68_energy_gain": energy_gain,
    }
