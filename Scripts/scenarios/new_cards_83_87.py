"""Runtime assertions for newly implemented Test83 through Test87."""

from __future__ import annotations

from collections import Counter


PREPARATION = "RD_MOD_POWER_PREPARATION_POWER"
FLIGHT = "RD_MOD_POWER_FLIGHT_POWER"
TEST85_POWER = "RD_MOD_POWER_TEST85_POWER"
TEST87_POWER = "RD_MOD_POWER_TEST87_POWER"
APPLE = "RD_MOD_CARD_APPLE_CIDER"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(pile + "_cards", [])
    return [card["card_id"] for card in cards]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def player_hp(snapshot):
    return int(combat(snapshot)["player"]["current_hp"])


def enemy_hp(snapshot):
    return int(combat(snapshot)["enemies"][0]["current_hp"])


def add_card(test, card_id):
    return test.run_console_command(
        "card " + card_id,
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
    add_card(test, "RD_MOD_CARD_TEST25")
    test.play_card("RD_MOD_CARD_TEST25", wait_for="end_turn")
    assert not hand(test.refresh())


def upgrade(test, card_id):
    card = test.find_hand_card(card_id)
    test.run_console_command(
        "upgrade " + str(card["index"]),
        wait_for="play_card",
    )
    upgraded = test.find_hand_card(card_id)
    assert upgraded["upgraded"], upgraded
    return upgraded


def run(test):
    results = {}
    test.enter_test_combat()

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST83")
    before_exhaust = Counter(pile_ids(test.refresh(), "exhaust"))
    test.play_card("RD_MOD_CARD_TEST83", wait_for="end_turn")
    after_test83 = test.refresh()
    after_exhaust = Counter(pile_ids(after_test83, "exhaust"))
    assert after_exhaust["RD_MOD_CARD_TEST3"] == before_exhaust["RD_MOD_CARD_TEST3"] + 1
    assert after_exhaust["RD_MOD_CARD_TEST4"] == before_exhaust["RD_MOD_CARD_TEST4"] + 1
    assert power_amount(after_test83, PREPARATION) == 2
    results["test83_exhausted"] = 2
    results["test83_preparation"] = 2

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST84")
    test.play_card("RD_MOD_CARD_TEST84", wait_for="end_turn")
    after_base84 = test.refresh()
    assert "RD_MOD_CARD_TEST3" in pile_ids(after_base84, "exhaust")
    assert power_amount(after_base84, FLIGHT) == 1
    results["test84_random_exhaust"] = True

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST84")
    upgrade(test, "RD_MOD_CARD_TEST84")
    test.play_card(
        "RD_MOD_CARD_TEST84",
        select_card_ids=["RD_MOD_CARD_TEST3"],
    )
    after_upgraded84 = test.refresh()
    assert "RD_MOD_CARD_TEST3" in pile_ids(after_upgraded84, "exhaust")
    assert any(card["card_id"] == "RD_MOD_CARD_TEST4" for card in hand(after_upgraded84))
    assert power_amount(after_upgraded84, FLIGHT) == 1
    results["test84_chosen_exhaust"] = True

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST85")
    upgraded85 = upgrade(test, "RD_MOD_CARD_TEST85")
    assert "固有" in upgraded85["resolved_rules_text"], upgraded85
    test.play_card("RD_MOD_CARD_TEST85", wait_for="end_turn")
    assert power_amount(test.refresh(), TEST85_POWER) == 1
    test.refresh()
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    assert any(card["card_id"] == APPLE for card in hand(next_turn))
    results["test85_start_turn_apple"] = True

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_TEST86")
    before86 = test.refresh()
    hp_before = enemy_hp(before86)
    test.play_card("RD_MOD_CARD_TEST86", target_index=0, wait_for="end_turn")
    dealt = hp_before - enemy_hp(test.refresh())
    assert dealt == 8, dealt
    results["test86_hits"] = 2
    results["test86_damage"] = dealt

    new_combat(test)
    discard_hand(test)
    control_before = test.refresh()
    control_hp = player_hp(control_before)
    test.refresh()
    test.client.end_turn()
    control_next = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    control_loss = control_hp - player_hp(control_next)
    assert control_loss > 0, control_loss

    new_combat(test)
    discard_hand(test)
    add_card(test, "RD_MOD_CARD_TEST87")
    upgraded87 = upgrade(test, "RD_MOD_CARD_TEST87")
    assert "固有" in upgraded87["resolved_rules_text"], upgraded87
    test.play_card("RD_MOD_CARD_TEST87", wait_for="end_turn")
    assert power_amount(test.refresh(), TEST87_POWER) == 1
    add_card(test, "RD_MOD_CARD_TEST3")
    add_card(test, "RD_MOD_CARD_TEST4")
    add_card(test, "RD_MOD_CARD_DEFEND")
    protected_before = test.refresh()
    protected_hp = player_hp(protected_before)
    test.refresh()
    test.client.end_turn()
    protected_next = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    protected_loss = protected_hp - player_hp(protected_next)
    assert protected_loss == max(control_loss - 3, 0), (
        control_loss,
        protected_loss,
    )
    results["test87_hand_cards"] = 3
    results["test87_damage_prevented"] = control_loss - protected_loss

    return results
