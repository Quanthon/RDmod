#!/usr/bin/env python3
"""Run one Python STS2 behavior-test scenario with the repository's MCP runtime."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="Python file containing run(test).")
    parser.add_argument("--health-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--runtime", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def find_mcp_root(workspace: Path) -> Path:
    candidates = sorted(
        workspace.glob(".tools/sts2-agent-v*/mcp_server"),
        key=lambda path: path.parent.name,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No .tools/sts2-agent-v*/mcp_server runtime was found.")
    return candidates[0]


def load_scenario(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("rdmod_runtime_scenario", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load scenario: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = getattr(module, "run", None)
    if not callable(run):
        raise TypeError(f"Scenario must define callable run(test): {path}")
    return run


def run_in_mcp_environment(args: argparse.Namespace, workspace: Path) -> int:
    mcp_root = find_mcp_root(workspace)
    command = [
        "uv",
        "run",
        "--project",
        str(mcp_root),
        "python",
        str(Path(__file__).resolve()),
        str(args.scenario.resolve()),
        "--health-timeout-seconds",
        str(args.health_timeout_seconds),
        "--runtime",
    ]
    return subprocess.run(command, cwd=workspace, check=False).returncode


def run_scenario(args: argparse.Namespace) -> int:
    from sts2_test_helper import Sts2TestHelper

    scenario_path = args.scenario.resolve()
    if not scenario_path.is_file():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")

    started = time.monotonic()
    test = Sts2TestHelper()
    test.wait_for_health(args.health_timeout_seconds)
    test.refresh()
    result = load_scenario(scenario_path)(test)
    elapsed = time.monotonic() - started
    print(f"RUNTIME_TEST_OK elapsed={elapsed:.3f}s scenario={scenario_path.name}")
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    return run_scenario(args) if args.runtime else run_in_mcp_environment(args, workspace)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RUNTIME_TEST_ERROR {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
