from __future__ import annotations

import argparse
import json
import os
import shutil
import xml.etree.ElementTree as ET
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from package_local_release import (  # noqa: E402
    build_release,
    resolve_release_version,
    validate_archive_entries,
    validate_release_version,
    write_manifest_version,
)


class PackageLocalReleaseTests(unittest.TestCase):
    def test_accepts_semantic_versions(self) -> None:
        self.assertEqual(validate_release_version("0.1.2"), "0.1.2")
        self.assertEqual(
            validate_release_version("0.2.0-beta.1"),
            "0.2.0-beta.1",
        )

    def test_accepts_prerelease_and_build_metadata(self) -> None:
        for value in ("1.0.0", "1.0.0-0", "1.0.0-beta.1", "1.0.0-01a",
                      "1.0.0+build.01", "1.0.0-rc.1+build.01"):
            with self.subTest(value=value):
                self.assertEqual(validate_release_version(value), value)

    def test_rejects_invalid_versions(self) -> None:
        for value in ("v0.1.2", "0.1", "0.1.2 beta", "", "0x3y0", "0/3/0",
                      "01.2.3", "1.02.3", "1.2.03", "1.0.0-01", "1.0.0-alpha.01",
                      "1.0.0-", "1.0.0+", "1.0.0+a..b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_release_version(value)

    def test_blank_prompt_keeps_current_version(self) -> None:
        with mock.patch("builtins.input", return_value=""):
            self.assertEqual(
                resolve_release_version("0.1.1", None, True),
                "0.1.1",
            )

    def test_manifest_version_write_is_atomic_and_preserves_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "RDmod.json"
            manifest = {"id": "RDMod", "version": "0.1.1", "name": "Rainbow Dash"}
            path.write_text(json.dumps(manifest), encoding="utf-8")

            write_manifest_version(path, manifest, "0.1.2")

            updated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updated["version"], "0.1.2")
            self.assertEqual(updated["id"], "RDMod")
            self.assertFalse(path.with_name(".RDmod.json.version.tmp").exists())


    def test_archive_contains_only_flat_rdmod_files(self) -> None:
        validate_archive_entries({"RDmod.dll", "RDmod.pck", "RDmod.json"})

    def test_archive_rejects_nested_or_extra_files(self) -> None:
        for entries in (
            {
                "mods/RDmod/RDmod.dll",
                "mods/RDmod/RDmod.pck",
                "mods/RDmod/RDmod.json",
            },
            {
                "RDmod.dll",
                "RDmod.pck",
                "RDmod.json",
                "STS2-RitsuLib.dll",
            },
        ):
            with self.subTest(entries=entries):
                with self.assertRaises(RuntimeError):
                    validate_archive_entries(entries)


    def test_build_rejects_nonzero_pck_export_even_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "RDmod.csproj"
            project.write_text("<Project />", encoding="utf-8")
            pck = workspace / "RDmod.pck"

            def failed_export(*args, **kwargs):
                pck.write_bytes(b"fresh but invalid")
                return subprocess.CompletedProcess(args[0], 1)

            with (
                mock.patch("package_local_release.run"),
                mock.patch(
                    "package_local_release.subprocess.run",
                    side_effect=failed_export,
                ),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                build_release(workspace, project, pck)



    def test_failed_build_restores_version_without_creating_archive(self) -> None:
        import package_local_release as release
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "Mod" / "RDmod.json"
            manifest.parent.mkdir()
            original = b'{"id":"RDMod","version":"0.3.0"}\n'
            manifest.write_bytes(original)
            args = argparse.Namespace(output_dir=root / "dist", skip_build=False,
                                      rdmod_version="1.0.0", prompt_version=False)
            with (
                mock.patch.object(release, "__file__", str(root / "Scripts" / "package_local_release.py")),
                mock.patch.object(release, "parse_args", return_value=args),
                mock.patch.object(release, "build_release", side_effect=subprocess.CalledProcessError(1, "export")),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                release.main()
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(list((root / "dist").glob("*.zip")), [])

    @unittest.skipUnless(os.name == "nt" and shutil.which("dotnet"), "Requires Windows and dotnet")
    def test_msbuild_propagates_export_failure_and_removes_partial_pck(self) -> None:
        source = ET.parse(SCRIPTS_DIR.parent / "Mod" / "RDmod.csproj")
        target = source.getroot().find("./Target[@Name='ExportPck']")
        self.assertIsNotNone(target)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pck = root / "partial.pck"
            helper = root / "fake_godot.cmd"
            helper.write_text('@echo off\necho incomplete>"%~6"\nexit /b 1\n', encoding="ascii")
            project = ET.Element("Project")
            properties = ET.SubElement(project, "PropertyGroup")
            ET.SubElement(properties, "GodotExe").text = str(helper)
            ET.SubElement(properties, "PckOutputPath").text = str(pck)
            project.append(target)
            path = root / "export.proj"
            ET.ElementTree(project).write(path, encoding="utf-8")
            result = subprocess.run(
                ["dotnet", "msbuild", str(path), "-t:ExportPck", "-nologo"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Godot PCK export failed with exit code 1", result.stdout)
            self.assertFalse(pck.exists(), "Failed export must remove its partial PCK")


if __name__ == "__main__":
    unittest.main()
