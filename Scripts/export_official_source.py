#!/usr/bin/env python3
"""Decompile the official game assembly and rebuild local reference indexes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ILSPY_VERSION = "9.1.0.7988"


def steam_libraries() -> list[Path]:
    candidates = [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam"), Path(r"D:\SteamLibrary"), Path(r"E:\SteamLibrary")]
    libraries: list[Path] = []
    for root in candidates:
        if root.is_dir() and root.resolve() not in libraries:
            libraries.append(root.resolve())
        config = root / "steamapps" / "libraryfolders.vdf"
        if config.is_file():
            for value in re.findall(r'^\s*"path"\s+"([^"]+)"', config.read_text(encoding="utf-8-sig"), re.MULTILINE):
                path = Path(value.replace(r"\\", "\\"))
                if path.is_dir() and path.resolve() not in libraries:
                    libraries.append(path.resolve())
    return libraries


def main() -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--install-tool", action="store_true")
    args = parser.parse_args()
    game_dir = args.game_dir
    if game_dir is None:
        game_dir = next((library / "steamapps" / "common" / "Slay the Spire 2" for library in steam_libraries() if (library / "steamapps" / "common" / "Slay the Spire 2" / "data_sts2_windows_x86_64" / "sts2.dll").is_file()), None)
    if game_dir is None:
        raise FileNotFoundError("Could not locate Slay the Spire 2. Pass --game-dir with the game root.")
    game_dir = game_dir.resolve()
    assembly = game_dir / "data_sts2_windows_x86_64" / "sts2.dll"
    if not assembly.is_file():
        raise FileNotFoundError(f"Game assembly not found: {assembly}")
    tool_dir = workspace / ".tools" / "ilspycmd"
    tool = tool_dir / "ilspycmd.exe"
    if not tool.is_file():
        if not args.install_tool:
            raise FileNotFoundError(f"ILSpy CLI is not installed at {tool}. Rerun with --install-tool.")
        tool_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["dotnet", "tool", "install", "ilspycmd", "--version", ILSPY_VERSION, "--tool-path", str(tool_dir)], check=True)
    output_dir = workspace / "OfficialReference" / "SlayTheSpire2"
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(tool), "--project", "--outputdir", str(output_dir), str(assembly)], check=True)
    if not any("MegaCrit.Sts2.Core.Models.Cards" in path.read_text(encoding="utf-8-sig", errors="ignore") for path in output_dir.rglob("*.cs")):
        raise RuntimeError(f"Export completed, but no official card source was found in {output_dir}")
    print(f"OFFICIAL_SOURCE_EXPORT_OK source={assembly} output={output_dir}")
    scripts = Path(__file__).resolve().parent
    subprocess.run([sys.executable, str(scripts / "build_official_card_index.py"), "--source-root", str(output_dir)], check=True)
    subprocess.run([sys.executable, str(scripts / "build_official_relic_index.py"), "--source-root", str(output_dir)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
