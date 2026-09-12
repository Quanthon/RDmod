#!/usr/bin/env python3
"""Extract official Simplified Chinese localization and rebuild indexes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


TOOL_VERSION = "2.6.3"
TOOL_URL = f"https://github.com/GDRETools/gdsdecomp/releases/download/v{TOOL_VERSION}/GDRE_tools-v{TOOL_VERSION}-windows.zip"


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Unsafe ZIP member: {member.filename}")
    archive.extractall(destination)


def main() -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--install-tool", action="store_true")
    args = parser.parse_args()
    if args.game_dir is None:
        settings = json.loads((workspace / ".vscode" / "settings.json").read_text(encoding="utf-8-sig"))
        game_dir = Path(settings["sts2.installDir"])
    else:
        game_dir = args.game_dir
    game_dir = game_dir.resolve()
    pck = game_dir / "SlayTheSpire2.pck"
    if not pck.is_file():
        raise FileNotFoundError(f"Official game PCK not found: {pck}")

    tool_dir = workspace / ".tools" / f"gdre-tools-v{TOOL_VERSION}"
    tool_zip = workspace / ".tools" / f"GDRE_tools-v{TOOL_VERSION}-windows.zip"
    tool = next(tool_dir.rglob("gdre_tools.exe"), None) if tool_dir.is_dir() else None
    if tool is None:
        if not args.install_tool:
            raise FileNotFoundError(f"GDRETools is not installed below {tool_dir}. Rerun with --install-tool.")
        tool_zip.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading GDRETools v{TOOL_VERSION} from its official GitHub release...")
        urllib.request.urlretrieve(TOOL_URL, tool_zip)
        tool_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tool_zip) as archive:
            safe_extract(archive, tool_dir)
        tool = next(tool_dir.rglob("gdre_tools.exe"), None)
        if tool is None:
            raise FileNotFoundError(f"gdre_tools.exe was not found after extracting {tool_zip}")

    localization_dir = workspace / "OfficialReference" / "localization" / "zhs"
    localization_dir.mkdir(parents=True, exist_ok=True)
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    for file_name in ("cards.json", "relics.json"):
        destination = localization_dir / file_name
        fresh = False
        try:
            with tempfile.TemporaryDirectory(prefix="rdmod-gdre-") as temporary:
                temp_dir = Path(temporary)
                subprocess.run([str(tool), "--headless", f"--extract={pck}", f"--output={temp_dir}", f"--include=res://localization/zhs/{file_name}"], check=True, creationflags=creation_flags)
                extracted = next((path for path in temp_dir.rglob(file_name) if path.as_posix().endswith(f"/localization/zhs/{file_name}")), None)
                if extracted is None:
                    raise FileNotFoundError(f"GDRETools completed, but localization/zhs/{file_name} was not extracted.")
                shutil.copy2(extracted, destination)
                fresh = True
        except Exception as exc:
            if not destination.is_file():
                raise
            print(f"WARNING: Fresh localization extraction failed for {file_name}: {exc}. Keeping {destination}.")
        print(f"OFFICIAL_LOCALIZATION_{'EXPORT' if fresh else 'CACHE'}_OK output={destination}")

    scripts = Path(__file__).resolve().parent
    subprocess.run([sys.executable, str(scripts / "build_official_card_index.py"), "--localization-path", str(localization_dir / "cards.json")], check=True)
    subprocess.run([sys.executable, str(scripts / "build_official_relic_index.py"), "--localization-path", str(localization_dir / "relics.json")], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
