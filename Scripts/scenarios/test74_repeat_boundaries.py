"""Verify Test74's repeat preview, hand limit, Charge exhaustion and hard cap."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from apple_cider_cards import add_card, upgrade, hand, pile_ids, combat, power_amount

CARD = "RD_MOD_CARD_TEST74"
DEFEND = "RD_MOD_CARD_DEFEND"
POWER = "RD_MOD_POWER_PREPARATION_POWER"

def clear_cards(test):
    for _ in range(100):
        snapshot = test.refresh()
        cards = hand(snapshot)
        if cards:
            test.run_console_command("remove_card " + cards[0]["card_id"], wait_for="end_turn")
        elif pile_ids(snapshot, "draw") or pile_ids(snapshot, "discard"):
            test.run_console_command("draw 1", wait_for="end_turn")
        else:
            return
    raise AssertionError("Failed to empty hand/draw/discard within 100 operations")

def run(test):
    results = []
    for label, charge, in_hand, in_draw, upgraded, repeats, expected_hand in (
        ("zero_charge", 0, 0, 8, False, 0, 0),
        ("charge_exhausted_upgraded", 3, 0, 8, True, 3, 6),
        ("full_hand", 3, 9, 8, False, 1, 10),
        ("hard_cap_empty_piles", 101, 0, 0, False, 100, 0),
    ):
        test.enter_test_combat()
        test.run_console_command("energy 99", wait_for="play_card")
        clear_cards(test)
        add_card(test, CARD)
        for _ in range(in_hand):
            add_card(test, DEFEND)
        for _ in range(in_draw):
            add_card(test, DEFEND, "draw")
        if upgraded:
            upgrade(test, CARD)
        if charge:
            test.run_console_command(f"power {POWER} {charge} 0", wait_for="play_card")
        before = test.refresh()
        card = test.find_hand_card(CARD, snapshot=before)
        text = card["resolved_rules_text"]
        assert re.search(r"(?:重复|Repeats )" + str(repeats) + r"(?:次| )", text), (label, "preview", repeats, text)
        result = test.play_card(CARD, wait_for="end_turn", timeout_seconds=90)
        after = result["after"]
        block = int(combat(after)["player"]["block"]) - int(combat(before)["player"]["block"])
        expected_block = repeats * (4 if upgraded else 2)
        assert block == expected_block, (label, "block", expected_block, block)
        assert power_amount(after, POWER) == charge - repeats, (label, "remaining charge", charge - repeats, power_amount(after, POWER))
        assert len(hand(after)) == expected_hand, (label, "hand", expected_hand, len(hand(after)))
        results.append({"case": label, "repeats": repeats, "block": block, "hand": expected_hand, "remaining_charge": charge - repeats})
    return results
