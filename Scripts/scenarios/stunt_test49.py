"""Runtime assertions for native Sly Stunt and Test49 enhancement."""

from __future__ import annotations


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(f"{pile}_cards", [])
    return [card["card_id"] for card in cards]


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def dynamic_value(card, name):
    return next(
        int(value["current_value"])
        for value in card["dynamic_values"]
        if value["name"] == name
    )


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def set_energy(test, amount=99):
    return test.run_console_command(f"energy {amount}", wait_for="play_card")


def new_combat(test):
    return test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)


def run(test):
    results = {}
    test.enter_test_combat()
    set_energy(test)

    # Native Sly: discarding Stunt auto-plays its two hits, then Exhaust removes it.
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_STUNT")
    before_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_STUNT"])
    after = test.refresh()
    after_hp = int(combat(after)["enemies"][0]["current_hp"])
    assert before_hp - after_hp == 8, ("Stunt Sly damage", before_hp, after_hp)
    assert "RD_MOD_CARD_STUNT" in pile_ids(after, "exhaust"), (
        "Stunt did not exhaust after Sly autoplay",
        pile_ids(after, "exhaust"),
    )
    results["stunt_sly_damage"] = before_hp - after_hp
    results["stunt_exhausted_after_sly"] = True

    # Test49 applies Retain to existing and future Stunts, and adds one damage hit.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_STUNT")
    add_card(test, "RD_MOD_CARD_TEST49")
    test.play_card("RD_MOD_CARD_TEST49")
    assert power_amount(test.refresh(), "RD_MOD_POWER_STUNT_ENHANCEMENT_POWER") == 1
    assert dynamic_value(test.find_hand_card("RD_MOD_CARD_STUNT"), "CalculatedHits") == 3
    add_card(test, "RD_MOD_CARD_STUNT")
    assert dynamic_value(test.find_hand_card("RD_MOD_CARD_STUNT", occurrence=1), "CalculatedHits") == 3
    test.client.end_turn()
    next_turn = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    retained = [card for card in combat(next_turn)["hand"] if card["card_id"] == "RD_MOD_CARD_STUNT"]
    assert len(retained) == 2, ("Test49 existing/future retain", len(retained))
    set_energy(test)
    before_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_STUNT", target_index=0)
    after_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    assert before_hp - after_hp == 12, ("Test49 extra Stunt hit", before_hp, after_hp)
    results["test49_retained_existing_and_future_stunts"] = len(retained)
    results["test49_stunt_damage"] = before_hp - after_hp

    # Upgraded Test49 applies two stacks at once, producing four total Stunt hits.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST49")
    test49 = test.find_hand_card("RD_MOD_CARD_TEST49")
    test.run_console_command(f"upgrade {test49['index']}", wait_for="play_card")
    test.play_card("RD_MOD_CARD_TEST49")
    assert power_amount(test.refresh(), "RD_MOD_POWER_STUNT_ENHANCEMENT_POWER") == 2
    add_card(test, "RD_MOD_CARD_STUNT")
    assert dynamic_value(test.find_hand_card("RD_MOD_CARD_STUNT"), "CalculatedHits") == 4
    before_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_STUNT", target_index=0)
    after_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    assert before_hp - after_hp == 16, ("upgraded Test49 extra Stunt hits", before_hp, after_hp)
    results["upgraded_test49_stunt_damage"] = before_hp - after_hp

    return results
