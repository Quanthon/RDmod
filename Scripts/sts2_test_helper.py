#!/usr/bin/env python3
"""Small primitives for state-driven STS2 runtime behavior tests."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable


PASSIVE_ACTIONS = {"save_and_quit"}


@dataclass(frozen=True)
class GameSnapshot:
    state: dict[str, Any]
    actions: list[dict[str, Any]]

    @property
    def action_names(self) -> set[str]:
        return {
            str(action.get("name"))
            for action in self.actions
            if isinstance(action, dict) and action.get("name")
        }


class Sts2TestHelper:
    """Refresh state around actions and stop polling as soon as a condition is met."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        poll_seconds: float = 0.25,
    ) -> None:
        if client is None:
            from sts2_mcp.client import Sts2Client

            client = Sts2Client()
        self.client = client
        self.poll_seconds = poll_seconds

    def wait_for_health(self, timeout_seconds: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                health = self.client.get_health()
                if health.get("status") == "ready":
                    return health
            except Exception as exc:
                last_error = exc
            time.sleep(self.poll_seconds)
        detail = f" Last error: {last_error}" if last_error else ""
        raise TimeoutError(f"STS2 did not become healthy within {timeout_seconds:.1f}s.{detail}")

    def refresh(self) -> GameSnapshot:
        return GameSnapshot(
            state=self.client.get_state(),
            actions=self.client.get_available_actions(),
        )

    def wait_for_action(
        self,
        action: str,
        *,
        timeout_seconds: float = 20.0,
        settle: bool = False,
    ) -> GameSnapshot:
        return self.wait_for_any_action(
            {action},
            timeout_seconds=timeout_seconds,
            settle=settle,
        )

    def wait_until_actionable(
        self,
        *,
        timeout_seconds: float = 20.0,
        settle: bool = False,
    ) -> GameSnapshot:
        return self.wait_until(
            lambda snapshot: bool(snapshot.action_names - PASSIVE_ACTIONS),
            description="an actionable game state",
            timeout_seconds=timeout_seconds,
            settle=settle,
        )

    def wait_for_any_action(
        self,
        actions: Iterable[str],
        *,
        timeout_seconds: float = 20.0,
        settle: bool = False,
    ) -> GameSnapshot:
        expected = {action for action in actions if action}
        if not expected:
            raise ValueError("At least one expected action is required.")

        return self.wait_until(
            lambda snapshot: bool(snapshot.action_names & expected),
            description=f"one of the actions {sorted(expected)}",
            timeout_seconds=timeout_seconds,
            settle=settle,
        )

    def wait_until(
        self,
        predicate: Callable[[GameSnapshot], bool],
        *,
        description: str,
        timeout_seconds: float = 20.0,
        settle: bool = False,
    ) -> GameSnapshot:
        deadline = time.monotonic() + timeout_seconds
        last_snapshot: GameSnapshot | None = None
        last_error: Exception | None = None
        may_accept = not settle
        while time.monotonic() < deadline:
            try:
                last_snapshot = self.refresh()
                last_error = None
                if may_accept and predicate(last_snapshot):
                    return last_snapshot
            except Exception as exc:
                last_error = exc

            may_accept = True
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(self.poll_seconds, remaining))

        found = sorted(last_snapshot.action_names) if last_snapshot else []
        detail = f"; last error: {last_error}" if last_error else ""
        raise TimeoutError(
            f"Timed out waiting for {description} after {timeout_seconds:.1f}s; "
            f"latest actions: {found}{detail}"
        )

    def continue_run(self, *, timeout_seconds: float = 30.0) -> GameSnapshot:
        current = self.refresh()
        if current.state.get("screen") != "MAIN_MENU":
            return current
        if "continue_run" not in current.action_names:
            raise RuntimeError(
                "No saved run can be continued; start a Rainbow Dash run before behavior testing."
            )

        self.client.continue_run()
        return self.wait_until(
            lambda snapshot: (
                snapshot.state.get("screen") != "MAIN_MENU"
                and bool(snapshot.action_names - PASSIVE_ACTIONS)
            ),
            description="the continued run to reach any actionable screen",
            timeout_seconds=timeout_seconds,
            settle=True,
        )

    def enter_test_combat(
        self,
        encounter_id: str = "BYRDONIS_ELITE",
        *,
        expected_character_id: str | None = "RD_MOD_CHARACTER_RAINBOW_DASH_CHARACTER",
        timeout_seconds: float = 30.0,
    ) -> GameSnapshot:
        self.wait_for_health(timeout_seconds)
        current = self.continue_run(timeout_seconds=timeout_seconds)
        run = current.state.get("run")
        if not isinstance(run, dict):
            raise RuntimeError("A run must be active before entering a test combat.")
        character_id = run.get("character_id")
        if expected_character_id is not None and character_id != expected_character_id:
            raise RuntimeError(
                f"Expected character {expected_character_id}, but the active run uses {character_id}."
            )

        result = self.run_console_command(
            f"fight {encounter_id}",
            wait_for="play_card",
            timeout_seconds=timeout_seconds,
        )
        if result.state.get("screen") != "COMBAT":
            raise RuntimeError(f"fight {encounter_id} did not enter combat.")
        return result

    def run_console_command(
        self,
        command: str,
        *,
        wait_for: str | Iterable[str] | None = None,
        timeout_seconds: float = 20.0,
    ) -> GameSnapshot:
        self.refresh()
        self.client.run_console_command(command)
        if wait_for is None:
            return self.refresh()
        expected = {wait_for} if isinstance(wait_for, str) else set(wait_for)
        return self.wait_for_any_action(
            expected,
            timeout_seconds=timeout_seconds,
            settle=True,
        )

    def find_hand_card(
        self,
        card_id: str,
        *,
        occurrence: int = 0,
        snapshot: GameSnapshot | None = None,
    ) -> dict[str, Any]:
        current = snapshot or self.refresh()
        combat = current.state.get("combat") or {}
        cards = [
            card
            for card in combat.get("hand", [])
            if isinstance(card, dict) and card.get("card_id") == card_id
        ]
        if occurrence < 0 or occurrence >= len(cards):
            raise LookupError(
                f"Hand contains {len(cards)} copies of {card_id}; occurrence {occurrence} is unavailable."
            )
        return cards[occurrence]

    def play_card(
        self,
        card_id: str,
        *,
        occurrence: int = 0,
        target_index: int | None = None,
        select_card_ids: Iterable[str] = (),
        wait_for: str | Iterable[str] = ("play_card", "resolve_rewards"),
        timeout_seconds: float = 20.0,
    ) -> dict[str, Any]:
        before = self.refresh()
        if "play_card" not in before.action_names:
            raise RuntimeError(f"play_card is unavailable; latest actions: {sorted(before.action_names)}")

        card = self.find_hand_card(card_id, occurrence=occurrence, snapshot=before)
        if not card.get("playable", False):
            raise RuntimeError(f"{card_id} is not playable: {card.get('unplayable_reason')}")
        if card.get("requires_target") and target_index is None:
            targets = card.get("valid_target_indices") or []
            if not targets:
                raise RuntimeError(f"{card_id} requires a target but exposes no valid target indices.")
            target_index = int(targets[0])

        response = self.client.play_card(int(card["index"]), target_index=target_index)
        selected_options: list[dict[str, Any]] = []
        for selected_card_id in select_card_ids:
            selecting = self.wait_for_action(
                "select_deck_card",
                timeout_seconds=timeout_seconds,
                settle=True,
            )
            selection = selecting.state.get("selection") or {}
            options = selection.get("cards") or []
            option = next(
                (
                    candidate
                    for candidate in options
                    if candidate.get("card_id") == selected_card_id
                ),
                None,
            )
            if option is None:
                available = [candidate.get("card_id") for candidate in options]
                raise LookupError(
                    f"Selection does not contain {selected_card_id}; available: {available}"
                )
            self.client.select_deck_card(int(option["index"]))
            selected_options.append(option)
        expected = {wait_for} if isinstance(wait_for, str) else set(wait_for)
        after = self.wait_for_any_action(
            expected,
            timeout_seconds=timeout_seconds,
            settle=True,
        )
        return {"before": before, "card": card, "response": response, "selected": selected_options, "after": after}
