#!/usr/bin/env python3
"""Build and package the three RDmod release files for ZIP sharing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path


REQUIRED_RDMOD_FILES = ("RDmod.dll", "RDmod.pck", "RDmod.json")


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Create a local-share ZIP containing only RDmod release files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=workspace / "dist",
        help="ZIP output directory; defaults to dist/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Package existing Release DLL and PCK without rebuilding.",
    )
    version = parser.add_mutually_exclusive_group()
    version.add_argument(
        "--version",
        dest="rdmod_version",
        help="Set the RDmod release version before packaging.",
    )
    version.add_argument(
        "--prompt-version",
        action="store_true",
        help="Prompt for the RDmod release version before packaging.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


VERSION_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def validate_release_version(value: str) -> str:
    version = value.strip()
    if not VERSION_RE.fullmatch(version):
        raise ValueError(
            "RDmod version must use semantic version format, for example "
            "0.1.2 or 0.2.0-beta.1."
        )
    return version


def resolve_release_version(
    current: str,
    requested: str | None,
    prompt: bool,
) -> str:
    value = requested
    if prompt:
        response = input(
            f"当前 RDmod 版本为 {current}。请输入本次打包版本号"
            f"（直接回车保持 {current}）："
        ).strip()
        value = response or current
    return validate_release_version(value or current)


def write_manifest_version(
    path: Path,
    manifest: dict,
    version: str,
) -> None:
    updated = dict(manifest)
    updated["version"] = version
    temporary = path.with_name(f".{path.name}.version.tmp")
    temporary.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run(command: list[str], workspace: Path) -> None:
    subprocess.run(command, cwd=workspace, check=True)


def build_release(workspace: Path, project_path: Path, pck_output: Path) -> None:
    pck_output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "dotnet",
            "build",
            str(project_path),
            "-c",
            "Release",
            "--nologo",
            "-p:SkipModInstall=true",
        ],
        workspace,
    )
    pck_output.unlink(missing_ok=True)
    export = subprocess.run(
        [
            "dotnet",
            "msbuild",
            str(project_path),
            "-t:ExportPck",
            "-p:Configuration=Release",
            f"-p:PckOutputPath={pck_output}",
            "-nologo",
        ],
        cwd=workspace,
        check=False,
    )
    if export.returncode != 0:
        raise subprocess.CalledProcessError(export.returncode, export.args)
    if not pck_output.is_file() or pck_output.stat().st_size == 0:
        raise FileNotFoundError(f"Godot did not produce a usable PCK: {pck_output}")


def add_file(archive: zipfile.ZipFile, source: Path, target: str) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required release file is missing: {source}")
    archive.write(source, target.replace("\\", "/"))


def validate_archive_entries(entries: set[str]) -> None:
    expected = set(REQUIRED_RDMOD_FILES)
    if entries != expected:
        raise RuntimeError(
            "Unexpected ZIP entries: "
            f"expected={sorted(expected)} actual={sorted(entries)}"
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parent.parent
    project_path = workspace / "Mod" / "RDmod.csproj"
    manifest_path = workspace / "Mod" / "RDmod.json"
    original_manifest = manifest_path.read_bytes()
    manifest = read_json(manifest_path)
    if manifest.get("id") != "RDMod":
        raise ValueError(f"Unexpected RDmod id in {manifest_path}")

    current_version = str(manifest.get("version") or "unknown")
    rdmod_version = resolve_release_version(
        current_version,
        args.rdmod_version,
        args.prompt_version,
    )
    version_changed = rdmod_version != current_version
    if version_changed:
        write_manifest_version(manifest_path, manifest, rdmod_version)
        print(f"RDMOD_VERSION_UPDATED {current_version} -> {rdmod_version}")

    try:
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        release_pck = output_dir / ".package" / "RDmod.pck"
        if not args.skip_build:
            build_release(workspace, project_path, release_pck)

        release_dll = (
            workspace
            / "Mod"
            / ".godot"
            / "mono"
            / "temp"
            / "bin"
            / "Release"
            / "RDmod.dll"
        )
        rdmod_sources = {
            "RDmod.dll": release_dll,
            "RDmod.pck": release_pck,
            "RDmod.json": manifest_path,
        }
        for name in REQUIRED_RDMOD_FILES:
            if not rdmod_sources[name].is_file():
                raise FileNotFoundError(
                    f"Required release file is missing: {rdmod_sources[name]}"
                )

        archive_path = output_dir / f"RainbowDash-{rdmod_version}.zip"
        archive_path.unlink(missing_ok=True)
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for name, source in rdmod_sources.items():
                add_file(archive, source, name)

        with zipfile.ZipFile(archive_path) as archive:
            entries = set(archive.namelist())
        try:
            validate_archive_entries(entries)
        except RuntimeError:
            archive_path.unlink(missing_ok=True)
            raise

        digest = sha256(archive_path)
        checksum_path = archive_path.with_suffix(
            archive_path.suffix + ".sha256"
        )
        checksum_path.write_text(
            f"{digest}  {archive_path.name}\n",
            encoding="ascii",
        )
        print(
            f"LOCAL_RELEASE_OK version={rdmod_version} "
            f"files={len(entries)} "
            f"bytes={archive_path.stat().st_size} zip={archive_path}"
        )
        print(f"SHA256 {digest}")
        print(f"CHECKSUM {checksum_path}")
        return 0
    except Exception:
        if version_changed:
            manifest_path.write_bytes(original_manifest)
            print(
                f"RDMOD_VERSION_ROLLED_BACK "
                f"{rdmod_version} -> {current_version}"
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())