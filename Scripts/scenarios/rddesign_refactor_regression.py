"""Runtime regression assertions for cards structurally changed by RDDesign migration."""

from __future__ import annotations


FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
OVERDRIVE = "RD_MOD_POWER_OVERDRIVE_POWER"
OVERDRIVE_REWARD = "RD_MOD_POWER_OVERDRIVE_REWARD_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next(
        (int(power["amount"]) for power in powers if power["power_id"] == power_id),
        0,
    )


def enemy_hp(snapshot):
    return int(combat(snapshot)["enemies"][0]["current_hp"])


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30
    )
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


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {PREPARATION} 3 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST74")
    upgrade(test, "RD_MOD_CARD_TEST74")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_TEST74", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 15, (hp_before, enemy_hp(after))
    assert power_amount(after, PREPARATION) == 0, combat(after)["player"]["powers"]
    assert len(hand(after)) == 7, [card["card_id"] for card in hand(after)]
    results["test74"] = {"damage": 15, "drawn": 7, "preparation": 0}

    new_combat(test)
    discard_hand(test)
    test.run_console_command(f"power {FLIGHT} 4 0", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST75")
    test.run_console_command("energy 1", wait_for="play_card")
    energy_before = int(combat(test.refresh())["player"]["energy"])
    test.play_card("RD_MOD_CARD_TEST75", wait_for="end_turn")
    after = test.refresh()
    energy_gain = int(combat(after)["player"]["energy"]) - energy_before
    assert power_amount(after, FLIGHT) == 0, combat(after)["player"]["powers"]
    assert energy_gain == 3, energy_gain
    results["test75"] = {"flight_consumed": 4, "net_energy": energy_gain}

    test.run_console_command(
        "fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30
    )
    test.run_console_command("heal 999", wait_for="play_card")
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST70")
    test.play_card("RD_MOD_CARD_TEST70", wait_for="end_turn")
    assert power_amount(test.refresh(), OVERDRIVE_REWARD) == 1
    assert int(combat(test.refresh())["player"]["energy"]) == 0
    add_card(test, "RD_MOD_CARD_TEST3")
    test.play_card("RD_MOD_CARD_TEST3", wait_for="end_turn")
    after = test.refresh()
    assert power_amount(after, PREPARATION) == 1, combat(after)["player"]["powers"]
    assert power_amount(after, FLIGHT) == 1, combat(after)["player"]["powers"]
    results["test70"] = {"preparation_reward": 1, "flight_reward": 1}

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST7")
    before = test.refresh()
    enemy_before = enemy_hp(before)
    player_before = int(combat(before)["player"]["current_hp"])
    test.play_card("RD_MOD_CARD_TEST7", target_index=0, wait_for="end_turn")
    after = test.refresh()
    enemy_damage = enemy_before - enemy_hp(after)
    self_damage = player_before - int(combat(after)["player"]["current_hp"])
    assert enemy_damage == 12, enemy_damage
    assert self_damage == 2, self_damage
    results["test7"] = {"enemy_damage": enemy_damage, "self_damage": self_damage}

    return results
