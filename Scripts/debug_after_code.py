#!/usr/bin/env python3
"""Build, install, launch, and verify RDmod with STS2-Agent."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


RD_MOD_SUCCESS_MARKERS = (
    "Finished mod initialization for 'Rainbow Dash' (RDMod).",
    "[RDMod] [Patcher - mechanics] All patches applied successfully",
    "[RDMod] Rainbow Dash Mod initialized.",
)
RD_MOD_FAILURE_MARKERS = (
    "Exception thrown when calling mod initializer of type RDmod.Scripts.Entry",
    "Default capability modifier is already registered: RDMod/",
)
NATIVE_KEYWORD_TEXT = {
    "Sly": "奇巧",
    "Retain": "保留",
    "Innate": "固有",
    "Exhaust": "消耗",
    "Ethereal": "虚无",
    "Unplayable": "无法打出",
    "Eternal": "永恒",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--startup-timeout-seconds", type=int, default=90)
    parser.add_argument("--export-pck", action="store_true")
    parser.add_argument("--skip-launch", action="store_true")
    return parser.parse_args()


def run_checked(arguments: list[str], *, cwd: Path) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def game_is_running() -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq SlayTheSpire2.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=True,
    )
    return "SlayTheSpire2.exe" in result.stdout


def stop_game() -> None:
    subprocess.run(
        ["taskkill", "/IM", "SlayTheSpire2.exe", "/T", "/F"],
        capture_output=True,
        check=True,
    )


def get_json_endpoint(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"http://127.0.0.1:8080{path}", timeout=5) as response:
        return json.load(response)


def response_data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else response


def validate_rdmod_log(text: str) -> tuple[bool, str | None]:
    for marker in RD_MOD_FAILURE_MARKERS:
        if marker in text:
            return False, marker
    missing = [marker for marker in RD_MOD_SUCCESS_MARKERS if marker not in text]
    return not missing, None


def latest_current_log(log_dir: Path, started_at: float) -> Path | None:
    candidates = [
        path
        for path in log_dir.glob("godot*.log")
        if path.is_file() and path.stat().st_mtime >= started_at - 5
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def validate_localization_json(localization_root: Path) -> int:
    paths = sorted(localization_root.rglob("*.json"))
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            relative = path.relative_to(localization_root)
            raise ValueError(
                f"Invalid localization JSON: {relative}:{exc.lineno}:{exc.colno}: {exc.msg}"
            ) from exc
    return len(paths)


def _registration_id(key: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake)
    return f"RD_MOD_CARD_{snake.upper()}"


def _native_keywords(source: str) -> set[str]:
    keywords: set[str] = set()
    canonical = re.search(
        r"CanonicalKeywords\s*=>\s*(.*?);",
        source,
        re.DOTALL,
    )
    if canonical:
        keywords.update(re.findall(r"CardKeyword\.([A-Za-z]+)", canonical.group(1)))
    keywords.update(re.findall(r"AddKeyword\(CardKeyword\.([A-Za-z]+)\)", source))
    return keywords


def _standalone_sentences(description: str) -> set[str]:
    without_tags = re.sub(r"\[[^\]]+\]", "", description)
    return {
        part.strip()
        for part in re.split(r"[。；\r\n]+", without_tags)
        if part.strip()
    }


def validate_native_keyword_localization(cards_dir: Path, cards_json: Path) -> int:
    localization = json.loads(cards_json.read_text(encoding="utf-8-sig"))
    if not isinstance(localization, dict):
        raise ValueError(f"Localization root must be an object: {cards_json}")

    checked = 0
    duplicates: list[str] = []
    for card_path in sorted(cards_dir.glob("*.cs")):
        source = card_path.read_text(encoding="utf-8-sig")
        if "[RegisterCard" not in source:
            continue
        checked += 1
        description = localization.get(
            f"{_registration_id(card_path.stem)}.description"
        )
        if not isinstance(description, str):
            continue
        sentences = _standalone_sentences(description)
        for keyword in sorted(_native_keywords(source)):
            native_text = NATIVE_KEYWORD_TEXT.get(keyword)
            if native_text and native_text in sentences:
                duplicates.append(f"{card_path.stem}: {keyword} ({native_text})")
    if duplicates:
        raise ValueError(
            "Native card keywords must not be repeated as standalone localization "
            "sentences; the game appends them automatically:\n"
            + "\n".join(duplicates)
        )
    return checked


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    project = workspace / "Mod" / "RDmod.csproj"
    settings_path = workspace / ".vscode" / "settings.json"
    agent_root = workspace / ".tools" / "sts2-agent-v0.9.1"
    mcp_root = agent_root / "mcp_server"

    if args.game_dir is None:
        settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        game_dir = Path(settings["sts2.installDir"])
    else:
        game_dir = args.game_dir
    game_dir = game_dir.resolve()
    game_exe = game_dir / "SlayTheSpire2.exe"

    localization_root = workspace / "Mod" / "RDMod" / "localization"
    localization_count = validate_localization_json(localization_root)
    print(f"[preflight] Validated {localization_count} localization JSON files.")
    checked_cards = validate_native_keyword_localization(
        workspace / "Mod" / "Cards",
        localization_root / "zhs" / "cards.json",
    )
    print(f"[preflight] Validated native keyword text for {checked_cards} cards.")

    if game_is_running():
        print("[0/6] Stopping the running game before installing updated assemblies...")
        stop_game()

    print("[1/6] Building and installing RDmod (Debug)...")
    run_checked(["dotnet", "build", str(project), "-c", "Debug", "--nologo"], cwd=workspace)

    if args.export_pck:
        print("[2/6] Exporting RDmod resource PCK...")
        pck_output = game_dir / "mods" / "RDmod" / "RDmod.pck"
        pck_output.unlink(missing_ok=True)
        export = subprocess.run(
            ["dotnet", "msbuild", str(project), "-t:ExportPck", "-p:Configuration=Debug", "--nologo"],
            cwd=workspace,
            check=False,
        )
        if export.returncode != 0:
            if not pck_output.is_file() or pck_output.stat().st_size == 0:
                raise subprocess.CalledProcessError(export.returncode, export.args)
            print(
                "PCK_EXPORT_WARNING "
                f"exit_code={export.returncode} fresh_pck={pck_output}"
            )
    else:
        print("[2/6] Skipping PCK export (pass --export-pck after resource changes).")

    print("[3/6] Checking installed artifacts and MCP import...")
    required = (
        game_dir / "mods" / "RDmod" / "RDmod.dll",
        game_dir / "mods" / "RDmod" / "RDmod.json",
        game_dir / "mods" / "STS2AIAgent" / "STS2AIAgent.dll",
        game_dir / "mods" / "STS2AIAgent" / "STS2AIAgent.pck",
        game_dir / "mods" / "STS2AIAgent" / "mod_id.json",
        mcp_root / "pyproject.toml",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required debug artifacts are missing:\n" + "\n".join(missing))
    run_checked(
        [
            "uv", "run", "--project", str(mcp_root), "python", "-c",
            "from sts2_mcp.server import create_server; create_server(); print('MCP_IMPORT_OK')",
        ],
        cwd=mcp_root,
    )

    if args.skip_launch:
        print("[4/6] Game launch skipped.")
        print("[5/6] Runtime endpoints skipped.")
        print("[6/6] Build-time checks passed.")
        return 0

    if not game_exe.is_file():
        raise FileNotFoundError(f"Game executable not found: {game_exe}")

    print("[4/6] Starting the game with development debug actions enabled...")
    started_at = time.time()
    environment = os.environ.copy()
    environment["STS2_ENABLE_DEBUG_ACTIONS"] = "1"
    subprocess.Popen([str(game_exe)], cwd=game_dir, env=environment)

    print("[5/6] Waiting for STS2-Agent endpoints...")
    deadline = time.monotonic() + args.startup_timeout_seconds
    last_error = "not started"
    health_data: dict[str, Any] = {}
    state_data: dict[str, Any] = {}
    actions_data: dict[str, Any] = {}
    log_ready = False
    log_path: Path | None = None
    app_data = os.environ.get("APPDATA")
    log_dir = Path(app_data) / "SlayTheSpire2" / "logs" if app_data else Path()

    while time.monotonic() < deadline:
        try:
            health = get_json_endpoint("/health")
            state = get_json_endpoint("/state")
            actions = get_json_endpoint("/actions/available")
            health_data = response_data(health)
            state_data = response_data(state)
            actions_data = response_data(actions)
            if health.get("ok") is False or state.get("ok") is False:
                raise RuntimeError("STS2-Agent returned an unsuccessful response.")
            if health_data.get("status") != "ready" or state_data.get("screen") in {None, "", "UNKNOWN"}:
                raise RuntimeError("STS2-Agent is reachable but game state is not ready.")

            log_path = latest_current_log(log_dir, started_at)
            if log_path is None:
                raise RuntimeError("Current game log is not available yet.")
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            log_ready, failure = validate_rdmod_log(log_text)
            if failure:
                raise RuntimeError(f"RDmod initialization failed: {failure}")
            if not log_ready:
                raise RuntimeError("RDmod initialization markers are incomplete.")
            break
        except Exception as exc:
            last_error = str(exc)
            if last_error.startswith("RDmod initialization failed:"):
                raise RuntimeError(last_error) from exc
            time.sleep(0.5)
    else:
        raise TimeoutError(
            f"Game verification did not complete within {args.startup_timeout_seconds} seconds. "
            f"Last error: {last_error}"
        )

    print("[6/6] RDmod initializer and patch log gates passed.")
    actions = actions_data.get("actions") or actions_data.get("available_actions") or []
    print(
        "AUTO_DEBUG_OK "
        f"health={health_data.get('status')} screen={state_data.get('screen')} "
        f"available_actions={len(actions)} rdmod=initialized log={log_path}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AUTO_DEBUG_ERROR {exc}", file=sys.stderr)
        raise SystemExit(1)

