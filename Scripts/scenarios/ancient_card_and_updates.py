"""Runtime assertions for updated cards and the new Ancient card."""

from __future__ import annotations


APPLE = "RD_MOD_CARD_APPLE_CIDER"
PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def power_amount(snapshot, power_id):
    return next(
        (
            int(power["amount"])
            for power in combat(snapshot)["player"]["powers"]
            if power["power_id"] == power_id
        ),
        0,
    )


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def new_combat(test, *, extra_energy=True):
    test.run_console_command(
        "fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30
    )
    test.run_console_command("heal 999", wait_for="play_card")
    if extra_energy:
        test.run_console_command("energy 99", wait_for="play_card")


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST25")
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    assert not hand(test.refresh())


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(f"upgrade {card['index']}", wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded


def enemy_hp(snapshot):
    return int(combat(snapshot)["enemies"][0]["current_hp"])


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    add_card(test, "RD_MOD_CARD_TEST12")
    before = test.refresh()
    block_before = int(combat(before)["player"]["block"])
    test.play_card("RD_MOD_CARD_TEST12")
    after = test.refresh()
    block_gain = int(combat(after)["player"]["block"]) - block_before
    assert block_gain == 11, block_gain
    results["test12_block"] = block_gain

    new_combat(test)
    add_card(test, "RD_MOD_CARD_ULTRA_CHARGE")
    card = test.find_hand_card("RD_MOD_CARD_ULTRA_CHARGE")
    assert "固有" in card["resolved_rules_text"], card["resolved_rules_text"]
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_ULTRA_CHARGE", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 20
    assert power_amount(after, PREPARATION) == 4
    results["ultra_charge"] = {"damage": 20, "preparation": 4, "innate": True}

    new_combat(test)
    add_card(test, "RD_MOD_CARD_ULTRA_CHARGE")
    upgrade(test, "RD_MOD_CARD_ULTRA_CHARGE")
    before = test.refresh()
    hp_before = enemy_hp(before)
    test.play_card("RD_MOD_CARD_ULTRA_CHARGE", target_index=0)
    after = test.refresh()
    assert hp_before - enemy_hp(after) == 25
    assert power_amount(after, PREPARATION) == 5
    results["ultra_charge_plus"] = {"damage": 25, "preparation": 5}

    new_combat(test, extra_energy=False)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST78")
    upgrade(test, "RD_MOD_CARD_TEST78")
    x_value = int(combat(test.refresh())["player"]["energy"])
    test.play_card("RD_MOD_CARD_TEST78")
    after_play = test.refresh()
    generated = [card for card in hand(after_play) if card["card_id"] == APPLE]
    assert len(generated) == x_value + 1, generated
    assert all(card["upgraded"] for card in generated), generated
    assert all("保留" in card["resolved_rules_text"] for card in generated), generated

    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    retained = [card for card in hand(next_turn) if card["card_id"] == APPLE]
    assert len(retained) == x_value + 1, retained
    assert all("保留" not in card["resolved_rules_text"] for card in retained), retained
    results["test78"] = {
        "x": x_value,
        "generated": x_value + 1,
        "retained_one_turn": True,
        "retain_removed_next_turn": True,
    }

    return results
