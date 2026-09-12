"""Runtime assertion for the Archaic Tooth Charge-to-UltraCharge mapping."""

from __future__ import annotations


CHARACTER_ID = "RD_MOD_CHARACTER_RAINBOW_DASH_CHARACTER"
CHARGE = "RD_MOD_CARD_CHARGE"
ULTRA_CHARGE = "RD_MOD_CARD_ULTRA_CHARGE"


def run(test):
    test.wait_for_health()
    current = test.continue_run()
    run_state = current.state.get("run")
    assert isinstance(run_state, dict), current.state.get("screen")
    assert run_state.get("character_id") == CHARACTER_ID, run_state

    before_cards = list(run_state.get("deck", []))
    charge_cards = [card for card in before_cards if card["card_id"] == CHARGE]
    ultra_before = sum(card["card_id"] == ULTRA_CHARGE for card in before_cards)
    assert charge_cards, before_cards
    expected_upgraded = bool(charge_cards[0]["upgraded"])

    chosen = None
    for _ in range(12):
        event_snapshot = test.run_console_command(
            "event OROBAS", wait_for="choose_event_option", timeout_seconds=30
        )
        event = event_snapshot.state.get("event") or {}
        option = next(
            (
                item
                for item in event.get("options", [])
                if "ARCHAIC_TOOTH" in str(item.get("text_key"))
            ),
            None,
        )
        if option is None:
            continue
        chosen = option
        test.refresh()
        test.client.choose_event_option(int(option["index"]))
        break

    assert chosen is not None, "Archaic Tooth did not appear in 12 forced Orobas events"
    after = test.refresh()
    after_cards = list((after.state.get("run") or {}).get("deck", []))
    transformed = [card for card in after_cards if card["card_id"] == ULTRA_CHARGE]
    assert sum(card["card_id"] == CHARGE for card in after_cards) == len(charge_cards) - 1
    assert len(transformed) == ultra_before + 1, transformed
    assert bool(transformed[-1]["upgraded"]) == expected_upgraded, transformed[-1]

    return {
        "option": chosen["text_key"],
        "charge_removed": 1,
        "ultra_charge_added": 1,
        "upgrade_preserved": True,
    }
