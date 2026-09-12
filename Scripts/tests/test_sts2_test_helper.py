from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sts2_test_helper import Sts2TestHelper  # noqa: E402


class FakeClient:
    def __init__(self, states: list[dict], actions: list[list[dict]]) -> None:
        self.states = states
        self.actions = actions
        self.read_index = 0
        self.played: tuple[int, int | None] | None = None
        self.selected: list[int] = []

    def get_state(self) -> dict:
        return self.states[min(self.read_index, len(self.states) - 1)]

    def get_available_actions(self) -> list[dict]:
        value = self.actions[min(self.read_index, len(self.actions) - 1)]
        self.read_index += 1
        return value

    def play_card(self, card_index: int, target_index: int | None = None) -> dict:
        self.played = (card_index, target_index)
        return {"accepted": True}


    def select_deck_card(self, option_index: int) -> dict:
        self.selected.append(option_index)
        return {"accepted": True}


class Sts2TestHelperTests(unittest.TestCase):
    def test_waits_for_fresh_action_without_fixed_delay(self) -> None:
        client = FakeClient(
            [{"state_version": 1}, {"state_version": 2}],
            [[], [{"name": "play_card"}]],
        )
        helper = Sts2TestHelper(client, poll_seconds=0)

        snapshot = helper.wait_for_action("play_card")

        self.assertEqual(2, snapshot.state["state_version"])
        self.assertEqual(2, client.read_index)

    def test_play_card_resolves_current_index_and_first_valid_target(self) -> None:
        hand = [{
            "index": 4,
            "card_id": "RD_MOD_CARD_TEST",
            "playable": True,
            "requires_target": True,
            "valid_target_indices": [2],
        }]
        client = FakeClient(
            [
                {"state_version": 7, "combat": {"hand": hand}},
                {"state_version": 8, "combat": {"hand": []}},
            ],
            [
                [{"name": "play_card"}],
                [{"name": "play_card"}],
            ],
        )
        helper = Sts2TestHelper(client, poll_seconds=0)

        result = helper.play_card("RD_MOD_CARD_TEST")

        self.assertEqual((4, 2), client.played)
        self.assertEqual(8, result["after"].state["state_version"])

    def test_play_card_selects_requested_cards_before_waiting_for_resolution(self) -> None:
        hand = [{
            "index": 4,
            "card_id": "RD_MOD_CARD_SOURCE",
            "playable": True,
            "requires_target": False,
        }]
        client = FakeClient(
            [
                {"state_version": 1, "combat": {"hand": hand}},
                {
                    "state_version": 2,
                    "selection": {
                        "cards": [
                            {"index": 7, "card_id": "RD_MOD_CARD_CHOICE"}
                        ]
                    },
                },
                {
                    "state_version": 2,
                    "selection": {
                        "cards": [
                            {"index": 7, "card_id": "RD_MOD_CARD_CHOICE"}
                        ]
                    },
                },
                {"state_version": 3, "combat": {"hand": []}},
                {"state_version": 3, "combat": {"hand": []}},
            ],
            [
                [{"name": "play_card"}],
                [{"name": "select_deck_card"}],
                [{"name": "select_deck_card"}],
                [{"name": "play_card"}],
                [{"name": "play_card"}],
            ],
        )
        helper = Sts2TestHelper(client, poll_seconds=0)

        result = helper.play_card(
            "RD_MOD_CARD_SOURCE",
            select_card_ids=["RD_MOD_CARD_CHOICE"],
        )

        self.assertEqual([7], client.selected)
        self.assertEqual("RD_MOD_CARD_CHOICE", result["selected"][0]["card_id"])
        self.assertEqual(3, result["after"].state["state_version"])


    def test_enters_test_combat_from_any_continued_run_screen(self) -> None:
        client = TestCombatFlowClient()
        helper = Sts2TestHelper(client, poll_seconds=0)

        snapshot = helper.enter_test_combat()

        self.assertEqual("COMBAT", snapshot.state["screen"])
        self.assertEqual(["fight BYRDONIS_ELITE"], client.console_commands)
        self.assertEqual(1, client.continue_calls)

class TestCombatFlowClient:
    def __init__(self) -> None:
        self.phase = "main"
        self.continue_calls = 0
        self.console_commands: list[str] = []

    def get_health(self) -> dict:
        return {"status": "ready"}

    def get_state(self) -> dict:
        if self.phase == "main":
            return {"screen": "MAIN_MENU", "run": None}
        if self.phase == "event":
            return {
                "screen": "EVENT",
                "run": {"character_id": "RD_MOD_CHARACTER_RAINBOW_DASH_CHARACTER"},
            }
        return {
            "screen": "COMBAT",
            "run": {"character_id": "RD_MOD_CHARACTER_RAINBOW_DASH_CHARACTER"},
            "combat": {"hand": []},
        }

    def get_available_actions(self) -> list[dict]:
        if self.phase == "main":
            return [{"name": "continue_run"}]
        if self.phase == "event":
            return [{"name": "choose_event_option"}, {"name": "save_and_quit"}]
        return [{"name": "play_card"}, {"name": "end_turn"}]

    def continue_run(self) -> dict:
        self.continue_calls += 1
        self.phase = "event"
        return {"accepted": True}

    def run_console_command(self, command: str) -> dict:
        self.console_commands.append(command)
        self.phase = "combat"
        return {"accepted": True}


if __name__ == "__main__":
    unittest.main()
