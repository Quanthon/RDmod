"""Runtime assertions for Test8's multi-hit damage and permanent Retain grant."""

from __future__ import annotations


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
        wait_for=("play_card", "end_turn"),
    )


def discard_hand(test):
    add_card(test, "RD_MOD_CARD_TEST88")
    test.play_card("RD_MOD_CARD_TEST88", wait_for="end_turn")
    assert not hand(test.refresh())


def enemy_durability(snapshot):
    enemy = combat(snapshot)["enemies"][0]
    return int(enemy["current_hp"]) + int(enemy["block"])


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command("upgrade " + str(card["index"]), wait_for="play_card")
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def end_turn(test):
    test.refresh()
    test.client.end_turn()
    return test.wait_for_action("play_card", timeout_seconds=30, settle=True)


def run_case(test, upgraded):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("heal 999", wait_for="play_card")
    test.run_console_command("energy 99", wait_for="play_card")
    discard_hand(test)
    test.run_console_command("block 100 1", wait_for="end_turn")
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST8")
    if upgraded:
        upgrade(test, "RD_MOD_CARD_TEST8")

    before = test.refresh()
    durability_before = enemy_durability(before)
    test.play_card(
        "RD_MOD_CARD_TEST8",
        target_index=0,
        wait_for="end_turn",
    )
    after = test.refresh()
    damage = durability_before - enemy_durability(after)
    expected_damage = 9 if upgraded else 6
    assert damage == expected_damage, (upgraded, damage)
    retained = test.find_hand_card("RD_MOD_CARD_TEST3", snapshot=after)
    assert "保留" in retained["resolved_rules_text"], retained

    next_turn = end_turn(test)
    retained_next_turn = test.find_hand_card("RD_MOD_CARD_TEST3", snapshot=next_turn)
    assert "保留" in retained_next_turn["resolved_rules_text"], retained_next_turn
    return expected_damage


def run(test):
    test.enter_test_combat()
    return {
        "base_damage": run_case(test, upgraded=False),
        "upgraded_damage": run_case(test, upgraded=True),
        "permanent_retain_base_and_upgrade": True,
    }
