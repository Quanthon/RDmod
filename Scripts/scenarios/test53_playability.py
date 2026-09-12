"""Runtime assertions for Test53 energy threshold and unplayable state."""

from __future__ import annotations


TEST53 = "RD_MOD_CARD_TEST53"
DEFEND = "RD_MOD_CARD_DEFEND"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def enemy_hps(snapshot):
    return [int(enemy["current_hp"]) for enemy in combat(snapshot)["enemies"]]


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def new_combat(test):
    test.run_console_command(
        "fight BYRDONIS_ELITE",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command("heal 999", wait_for="play_card")
    return test.run_console_command("energy 99", wait_for="play_card")


def play_defends(test, count):
    for _ in range(count):
        add_card(test, DEFEND)
        test.play_card(DEFEND, wait_for="play_card")


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
    add_card(test, TEST53)
    blocked = test.find_hand_card(TEST53)
    assert not blocked["playable"], blocked
    reason = blocked.get("unplayable_reason")
    assert reason, blocked
    try:
        response = test.client.play_card(int(blocked["index"]))
        attempt_result = str(response)
    except Exception as exc:
        attempt_result = str(exc)
    after_attempt = test.refresh()
    assert any(card["card_id"] == TEST53 for card in hand(after_attempt))
    results["blocked"] = {
        "playable": False,
        "reason": reason,
        "attempt": attempt_result,
    }

    new_combat(test)
    play_defends(test, 7)
    add_card(test, TEST53)
    base = test.find_hand_card(TEST53)
    assert base["playable"], base
    assert "当前耗能总和：7" in base["resolved_rules_text"], base
    before = test.refresh()
    hp_before = enemy_hps(before)
    energy_before = int(combat(before)["player"]["energy"])
    test.play_card(TEST53, wait_for=("play_card", "resolve_rewards"))
    after = test.refresh()
    hp_after = enemy_hps(after)
    assert all(start - end == 50 for start, end in zip(hp_before, hp_after))
    energy_gain = int(combat(after)["player"]["energy"]) - energy_before
    assert energy_gain == 5, energy_gain
    results["base"] = {"damage": 50, "energy": energy_gain}

    new_combat(test)
    play_defends(test, 7)
    add_card(test, TEST53)
    upgraded = upgrade(test, TEST53)
    assert upgraded["playable"], upgraded
    before = test.refresh()
    hp_before = enemy_hps(before)
    energy_before = int(combat(before)["player"]["energy"])
    test.play_card(TEST53, wait_for=("play_card", "resolve_rewards"))
    after = test.refresh()
    hp_after = enemy_hps(after)
    assert all(start - end == 60 for start, end in zip(hp_before, hp_after))
    energy_gain = int(combat(after)["player"]["energy"]) - energy_before
    assert energy_gain == 6, energy_gain
    results["upgraded"] = {"damage": 60, "energy": energy_gain}

    return results