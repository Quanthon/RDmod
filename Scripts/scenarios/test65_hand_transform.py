"""Verify Test65 transforms only hand Status cards, in both upgrade states."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
from apple_cider_cards import add_card, discard_hand, upgrade, hand, pile_ids

CARD = "RD_MOD_CARD_TEST65"
STATUS = "RD_MOD_CARD_OUT_OF_CONTROL"
APPLE = "RD_MOD_CARD_APPLE_CIDER"
DEFEND = "RD_MOD_CARD_DEFEND"

def run(test):
    results = []
    for upgraded in (False, True):
        test.enter_test_combat()
        test.run_console_command("energy 99", wait_for="play_card")
        discard_hand(test)
        add_card(test, CARD)
        for pile in ("draw", "discard", "exhaust"):
            add_card(test, STATUS, pile)
        for card in (STATUS, STATUS, DEFEND):
            add_card(test, card)
        if upgraded:
            upgrade(test, CARD)
        before = test.refresh()
        source = test.find_hand_card(CARD, snapshot=before)
        assert int(source["energy_cost"]) == (0 if upgraded else 1), source
        piles = {pile: Counter(pile_ids(before, pile)) for pile in ("draw", "discard", "exhaust")}
        result = test.play_card(CARD, wait_for="end_turn")
        after = result["after"]
        ids = Counter(c["card_id"] for c in hand(after))
        assert ids == Counter({APPLE: 2, DEFEND: 1}), ("hand transformation", ids)
        assert all(not c["upgraded"] for c in hand(after) if c["card_id"] == APPLE), hand(after)
        for pile in piles:
            actual = Counter(pile_ids(after, pile))
            expected = piles[pile] + (Counter({CARD: 1}) if pile == "discard" else Counter())
            assert actual == expected, ("outside hand unchanged", pile, expected, actual)
        add_card(test, CARD)
        test.play_card(CARD, wait_for="end_turn")
        assert Counter(c["card_id"] for c in hand(test.refresh())) == ids, "No statuses must be a no-op"
        results.append({"upgraded": upgraded, "transformed": 2, "other_piles_unchanged": True, "empty_status_noop": True})
    return results
