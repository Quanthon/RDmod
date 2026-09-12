"""Runtime assertions for Test40's four-card generated selection."""

from __future__ import annotations


CARD_ID = "RD_MOD_CARD_TEST40"


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def hand(snapshot):
    return combat(snapshot).get("hand", [])


def run(test):
    test.enter_test_combat()
    test.run_console_command("energy 99", wait_for="play_card")
    test.run_console_command(f"card {CARD_ID}", wait_for="play_card")
    source = test.find_hand_card(CARD_ID)
    test.run_console_command(f"upgrade {source['index']}", wait_for="play_card")
    source = test.find_hand_card(CARD_ID)
    assert source["upgraded"], source

    test.client.play_card(int(source["index"]))
    selecting = test.wait_for_action("select_deck_card", timeout_seconds=20, settle=True)
    options = selecting.state["selection"]["cards"]
    assert len(options) == 4, ("Test40 choice count", len(options), options)
    assert all(option["upgraded"] for option in options), ("Test40 upgraded choices", options)

    chosen = options[0]
    test.client.select_deck_card(int(chosen["index"]))
    resolved = test.wait_for_action("play_card", timeout_seconds=20, settle=True)
    generated = [
        card
        for card in hand(resolved)
        if card["card_id"] == chosen["card_id"]
        and card["upgraded"]
        and "可以超速打出" in card["resolved_rules_text"]
    ]
    assert generated, ("Test40 selected card was not added with temporary Overdrive", chosen, hand(resolved))
    assert not any(card["card_id"] == CARD_ID for card in hand(resolved)), "Test40 did not exhaust"
    return {
        "test40_choice_count": len(options),
        "test40_selected_card": chosen["card_id"],
        "test40_selected_upgraded": True,
        "test40_selected_has_temporary_overdrive": True,
    }
