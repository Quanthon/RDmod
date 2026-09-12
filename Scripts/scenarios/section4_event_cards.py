"""Runtime assertions for section 4 event and turn-count representative cards."""

from __future__ import annotations


def combat(snapshot):
    value = snapshot.state.get("combat")
    assert isinstance(value, dict), ("missing combat", snapshot.state.get("screen"))
    return value


def power_amount(snapshot, power_id):
    powers = combat(snapshot)["player"]["powers"]
    return next((int(power["amount"]) for power in powers if power["power_id"] == power_id), 0)


def pile_ids(snapshot, pile):
    view = snapshot.state.get("agent_view") or {}
    cards = (view.get("combat") or {}).get(f"{pile}_cards", [])
    return [card["card_id"] for card in cards]


def pile_count(snapshot, pile):
    return len(pile_ids(snapshot, pile))


def add_card(test, card_id):
    return test.run_console_command(f"card {card_id}", wait_for="play_card")


def set_energy(test, amount=99):
    return test.run_console_command(f"energy {amount}", wait_for="play_card")


def new_combat(test):
    return test.run_console_command("fight BYRDONIS_ELITE", wait_for="play_card", timeout_seconds=30)


def run(test):
    results = {}
    test.enter_test_combat()

    # Test24: the temporary listener sees subsequent non-attacks and expires at turn end.
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST24")
    test.play_card("RD_MOD_CARD_TEST24")
    before = power_amount(test.refresh(), "RD_MOD_POWER_PREPARATION_POWER")
    assert before == 0, ("Test24 triggered itself", before)
    add_card(test, "RD_MOD_CARD_DEFEND")
    test.play_card("RD_MOD_CARD_DEFEND")
    after = power_amount(test.refresh(), "RD_MOD_POWER_PREPARATION_POWER")
    assert after == before + 1, ("Test24 non-attack trigger", before, after)
    results["test24_preparation_gain"] = after - before

    # Test47: Token rarity is the shared generated-card predicate; playing a Shiv draws once.
    add_card(test, "RD_MOD_CARD_TEST47")
    test.play_card("RD_MOD_CARD_TEST47")
    add_card(test, "SHIV")
    before_draw = pile_count(test.refresh(), "draw")
    test.play_card("SHIV")
    after_draw = pile_count(test.refresh(), "draw")
    assert after_draw == before_draw - 1, ("Test47 generated draw", before_draw, after_draw)
    results["test47_cards_drawn"] = before_draw - after_draw

    # Test48 + Test69: discarding a Status exhausts it and Daisy draws once.
    add_card(test, "RD_MOD_CARD_TEST48")
    test.play_card("RD_MOD_CARD_TEST48")
    add_card(test, "RD_MOD_CARD_TEST69")
    test.play_card("RD_MOD_CARD_TEST69")
    add_card(test, "RD_MOD_CARD_TAKE_OFF")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    before_draw = pile_count(test.refresh(), "draw")
    test.play_card("RD_MOD_CARD_TAKE_OFF", select_card_ids=["RD_MOD_CARD_OUT_OF_CONTROL"])
    snapshot = test.refresh()
    after_draw = pile_count(snapshot, "draw")
    assert "RD_MOD_CARD_OUT_OF_CONTROL" in pile_ids(snapshot, "exhaust"), (
        "Test48 discarded status not exhausted",
        pile_ids(snapshot, "exhaust"),
    )
    assert after_draw == before_draw - 1, ("Test69 discard draw", before_draw, after_draw)
    results["test48_status_exhausted"] = True
    results["test69_cards_drawn"] = before_draw - after_draw

    # Test69 damage modifier is checked in isolation to avoid Preparation changing the base hit.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST69")
    test.play_card("RD_MOD_CARD_TEST69")
    shrink = next(
        (
            power
            for power in combat(test.refresh())["player"]["powers"]
            if power["power_id"] in {"SHRINK", "SHRINK_POWER"}
        ),
        None,
    )
    assert shrink is not None and int(shrink["amount"]) == -1, (
        "Test69 permanent Shrink",
        combat(test.refresh())["player"]["powers"],
    )
    add_card(test, "RD_MOD_CARD_STRIKE")
    before_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    test.play_card("RD_MOD_CARD_STRIKE", target_index=0)
    after_hp = int(combat(test.refresh())["enemies"][0]["current_hp"])
    assert before_hp - after_hp == 4, ("Test69 damage reduction", before_hp, after_hp)
    results["test69_shrink_amount"] = int(shrink["amount"])
    results["test69_reduced_six_damage_to"] = before_hp - after_hp

    # Test42 + Test50: end-turn Flight damage and card-sourced OutOfControl self-damage.
    new_combat(test)
    set_energy(test)
    add_card(test, "RD_MOD_CARD_TEST42")
    test.play_card("RD_MOD_CARD_TEST42")
    add_card(test, "RD_MOD_CARD_TEST50")
    test.play_card("RD_MOD_CARD_TEST50")
    test.run_console_command("power RD_MOD_POWER_FLIGHT_POWER 1 0", wait_for="play_card")
    add_card(test, "RD_MOD_CARD_OUT_OF_CONTROL")
    before_hp = {enemy["enemy_id"]: enemy["current_hp"] for enemy in combat(test.refresh())["enemies"]}
    test.client.end_turn()
    ended = test.wait_for_action("play_card", timeout_seconds=30, settle=True)
    after_enemies = {enemy["enemy_id"]: enemy["current_hp"] for enemy in combat(ended)["enemies"]}
    for enemy_id, hp in before_hp.items():
        assert after_enemies[enemy_id] == hp - 5, (
            "Test42 end-turn damage",
            enemy_id,
            hp,
            after_enemies[enemy_id],
        )
    strength = power_amount(ended, "STRENGTH_POWER")
    assert strength == 1, ("Test50 card self-damage strength", strength)
    results["test42_damage_per_enemy"] = 5
    results["test50_strength_gain"] = strength

    # Test53: four normally paid 3-cost cards produce an EnergyValue total of 12.
    new_combat(test)
    set_energy(test)
    for _ in range(4):
        add_card(test, "RD_MOD_CARD_TEST3")
        test.play_card("RD_MOD_CARD_TEST3", target_index=0)
    add_card(test, "RD_MOD_CARD_TEST53")
    before = test.refresh()
    before_energy = int(combat(before)["player"]["energy"])
    before_hp = {enemy["enemy_id"]: enemy["current_hp"] for enemy in combat(before)["enemies"]}
    test.play_card("RD_MOD_CARD_TEST53")
    after = test.refresh()
    after_energy = int(combat(after)["player"]["energy"])
    after_hp = {enemy["enemy_id"]: enemy["current_hp"] for enemy in combat(after)["enemies"]}
    assert after_energy == before_energy + 5, ("Test53 net energy", before_energy, after_energy)
    for enemy_id, hp in before_hp.items():
        assert after_hp[enemy_id] == hp - 50, ("Test53 all-enemy damage", enemy_id, hp, after_hp[enemy_id])
    results["test53_damage"] = 50
    results["test53_net_energy"] = after_energy - before_energy

    return results
