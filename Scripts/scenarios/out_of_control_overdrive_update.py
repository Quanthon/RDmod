"""Runtime assertions for OutOfControl damage and Overdrive-generated OutOfControl."""

from __future__ import annotations


OUT_OF_CONTROL = "RD_MOD_CARD_OUT_OF_CONTROL"
TEST3 = "RD_MOD_CARD_TEST3"
TEST25 = "RD_MOD_CARD_TEST25"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def run(test):
    test.enter_test_combat()
    test.run_console_command("heal 999", wait_for="play_card")

    add_card(test, TEST25)
    test.play_card(TEST25, wait_for="end_turn")
    assert not hand(test.refresh())

    add_card(test, TEST3)
    before_out_of_control = sum(card["card_id"] == OUT_OF_CONTROL for card in hand(test.refresh()))
    result = test.play_card(TEST3, target_index=0)
    after_play = result["after"]
    out_of_control_cards = [card for card in hand(after_play) if card["card_id"] == OUT_OF_CONTROL]
    assert len(out_of_control_cards) - before_out_of_control == 1, out_of_control_cards
    assert all("2" in card["resolved_rules_text"] for card in out_of_control_cards), out_of_control_cards

    player = combat(after_play)["player"]
    hp_before = int(player["current_hp"])
    block_before = int(player["block"])
    intent_damage = int(combat(after_play)["enemies"][0]["intents"][0]["total_damage"])
    test.client.end_turn()
    after_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    hp_loss = hp_before - int(combat(after_turn)["player"]["current_hp"])
    expected_hp_loss = max(0, intent_damage + 2 - block_before)
    assert hp_loss == expected_hp_loss, {
        "hp_loss": hp_loss,
        "expected": expected_hp_loss,
        "intent_damage": intent_damage,
        "block_before": block_before,
    }

    return {
        "overdrive_out_of_control_added": 1,
        "out_of_control_damage": 2,
        "enemy_intent_damage": intent_damage,
        "block_before": block_before,
        "hp_loss": hp_loss,
    }
