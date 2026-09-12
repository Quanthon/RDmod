"""Runtime assertion that Test86 has no redundant combat-only hit-count note."""

from __future__ import annotations


TEST86 = "RD_MOD_CARD_TEST86"


def run(test):
    test.enter_test_combat()
    test.run_console_command(
        "fight CULTISTS_NORMAL",
        wait_for="play_card",
        timeout_seconds=30,
    )
    test.run_console_command(f"card {TEST86}", wait_for="play_card")
    card = test.find_hand_card(TEST86)
    rules = card["resolved_rules_text"]
    assert "随机对敌人造成8点伤害3次" in rules, rules
    assert "（攻击" not in rules, rules
    return {"rules": rules, "combat_note_removed": True}