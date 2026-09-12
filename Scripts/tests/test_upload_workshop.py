from __future__ import annotations
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upload_workshop as flow


class WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'workshop'
        self.folder.mkdir()
        self.exe = self.root / 'ModUploader.exe'
        self.exe.touch()
        self.metadata = {'title': 'Rainbow Dash', 'visibility': 'private', 'dependencies': [flow.RITSULIB_ID]}
        self.manifest = {'id': 'RDMod', 'version': '1.0.0'}
        self.settings = {'uploader': str(self.exe), 'description_file': 'description.txt', 'change_note_file': None}
        self.json('workshop.json', self.metadata)
        self.json('settings.json', self.settings)
        (self.folder / 'description.txt').write_text('中文\nEnglish', encoding='utf-8')
        from PIL import Image
        Image.new('RGB', (2, 2)).save(self.folder / 'image.png')
        self.archive = self.root / 'release.zip'
        self.make_archive()

    def json(self, name, value):
        (self.folder / name).write_text(json.dumps(value), encoding='utf-8')

    def make_archive(self, extra=None, version='1.0.0'):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('RDmod.dll', b'dll')
            archive.writestr('RDmod.pck', b'pck')
            archive.writestr('RDmod.json', json.dumps({**self.manifest, 'version': version}))
            if extra:
                archive.writestr(extra, b'extra')
        self.archive.with_suffix('.zip.sha256').write_text(flow.sha256(self.archive) + '  release.zip\n')

    def test_text_files_merge_and_null_preserves_online_fields(self):
        metadata, executable = flow.load_metadata(self.folder)
        self.assertEqual(metadata['description'], '中文\nEnglish')
        self.assertNotIn('changeNote', metadata)
        self.assertEqual(executable, self.exe)
        self.settings['description_file'] = None
        self.json('settings.json', self.settings)
        self.assertNotIn('description', flow.load_metadata(self.folder)[0])

    def test_invalid_metadata_and_dependency_rejected(self):
        for change in ({'visibility': 'invalid'}, {'dependencies': []},
                       {'dependencies': [str(flow.RITSULIB_ID)]}, {'tags': 'Characters'},
                       {'typo': True}, {'contentDescriptors': ['bad']}):
            self.json('workshop.json', {**self.metadata, **change})
            with self.subTest(change=change), self.assertRaises(ValueError):
                flow.load_metadata(self.folder)

    def test_missing_oversized_and_corrupt_cover_rejected(self):
        image = self.folder / 'image.png'
        for data in (b'not png', b'\x89PNG\r\n\x1a\n', b'\x89PNG\r\n\x1a\n' + b'x' * 1_000_000):
            image.write_bytes(data)
            with self.subTest(length=len(data)), self.assertRaises((ValueError, OSError)):
                flow.load_metadata(self.folder)
        image.unlink()
        with self.assertRaises(FileNotFoundError):
            flow.load_metadata(self.folder)

    def test_staging_exact_files_and_identity_recovery(self):
        flow.save_item_id(self.folder, '1234')
        (self.folder / 'mod_id.txt').unlink()
        stage = flow.stage_archive(self.folder, self.archive, self.manifest, self.metadata)
        self.assertEqual({p.name for p in (stage / 'content').iterdir()}, {'RDmod.dll', 'RDmod.pck', 'RDmod.json'})
        self.assertEqual((stage / 'mod_id.txt').read_text().strip(), '1234')
        self.assertEqual((self.folder / 'mod_id.txt').read_text().strip(), '1234')
        self.assertEqual(flow.read_item_id(self.folder), '1234')

    def test_mismatched_identity_rejected(self):
        flow.save_item_id(self.folder, '1234')
        (self.folder / 'mod_id.txt').write_text('5678')
        with self.assertRaises(ValueError):
            flow.read_item_id(self.folder)

    def test_wrong_archive_rejected_before_staging(self):
        for extra, version in [('extra.txt', '1.0.0'), (None, '0.3.0')]:
            self.make_archive(extra, version)
            with self.assertRaises((ValueError, RuntimeError)):
                flow.stage_archive(self.folder, self.archive, self.manifest, self.metadata)
            self.assertFalse((self.folder / '.upload').exists())
        self.make_archive()
        self.archive.with_suffix('.zip.sha256').write_text('BAD')
        with self.assertRaises(ValueError):
            flow.stage_archive(self.folder, self.archive, self.manifest, self.metadata)

    def test_failed_upload_preserves_new_identity_for_retry(self):
        stage = flow.stage_archive(self.folder, self.archive, self.manifest, self.metadata)
        process = mock.Mock(stdout=io.StringIO("Uploading 'RD' to the steam workshop with item ID 1234...\nError\n"))
        process.wait.return_value = 1
        with mock.patch.object(flow.subprocess, 'Popen', return_value=process), self.assertRaises(subprocess.CalledProcessError):
            flow.upload(self.folder, stage, self.exe)
        self.assertEqual(flow.read_item_id(self.folder), '1234')
        self.assertTrue((self.folder / 'upload-pending.txt').exists())

    def test_unknown_first_upload_outcome_blocks_duplicate_creation(self):
        (self.folder / 'upload-pending.txt').write_text('unknown')
        with mock.patch.object(flow.subprocess, 'Popen') as launch, self.assertRaises(ValueError):
            flow.upload(self.folder, self.folder / '.upload', self.exe)
        launch.assert_not_called()

    def test_success_keeps_identity_and_clears_pending(self):
        stage = flow.stage_archive(self.folder, self.archive, self.manifest, self.metadata)
        (stage / 'mod_id.txt').write_text('1234')
        process = mock.Mock(stdout=io.StringIO('Successfully uploaded RD with id 1234!\n'))
        process.wait.return_value = 0
        with mock.patch.object(flow.subprocess, 'Popen', return_value=process):
            flow.upload(self.folder, stage, self.exe)
        self.assertEqual(flow.read_item_id(self.folder), '1234')
        self.assertFalse((self.folder / 'upload-pending.txt').exists())

    def test_prepare_builds_without_uploading(self):
        manifest = self.root / 'Mod' / 'RDmod.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps(self.manifest))
        target = self.root / 'dist' / 'RainbowDash-1.0.0.zip'
        target.parent.mkdir()
        target.write_bytes(self.archive.read_bytes())
        target.with_suffix('.zip.sha256').write_text(flow.sha256(target))
        with (mock.patch.object(flow, 'ROOT', self.root), mock.patch.object(flow, 'WORKSHOP', self.folder),
              mock.patch.object(sys, 'argv', ['upload_workshop.py', '--prepare']),
              mock.patch.object(flow, 'validate_localization_json'),
              mock.patch.object(flow, 'validate_native_keyword_localization'),
              mock.patch.object(flow.subprocess, 'run') as build,
              mock.patch.object(flow, 'upload') as upload):
            self.assertEqual(flow.main(), 0)
        build.assert_called_once()
        upload.assert_not_called()
        self.assertTrue((self.folder / '.upload/content/RDmod.dll').exists())
        self.assertFalse((self.folder / '.workflow.lock').exists())

    def test_default_check_does_not_build_or_upload(self):
        manifest = self.root / 'Mod' / 'RDmod.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps(self.manifest))
        with (mock.patch.object(flow, 'ROOT', self.root), mock.patch.object(flow, 'WORKSHOP', self.folder),
              mock.patch.object(sys, 'argv', ['upload_workshop.py']),
              mock.patch.object(flow.subprocess, 'run') as build,
              mock.patch.object(flow, 'upload') as upload):
            self.assertEqual(flow.main(), 0)
        build.assert_not_called()
        upload.assert_not_called()
        self.assertFalse((self.folder / '.workflow.lock').exists())

    def test_github_failure_stops_before_steam_upload(self):
        import publish_github
        self.settings['github'] = {'repository': 'Quanthon/RDmod', 'cli': str(self.exe)}
        self.json('settings.json', self.settings)
        manifest = self.root / 'Mod' / 'RDmod.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps(self.manifest))
        target = self.root / 'dist' / 'RainbowDash-1.0.0.zip'
        target.parent.mkdir()
        target.write_bytes(self.archive.read_bytes())
        target.with_suffix('.zip.sha256').write_text(flow.sha256(target))
        with (mock.patch.object(flow, 'ROOT', self.root), mock.patch.object(flow, 'WORKSHOP', self.folder),
              mock.patch.object(sys, 'argv', ['upload_workshop.py', '--upload']),
              mock.patch.object(flow, 'validate_localization_json'),
              mock.patch.object(flow, 'validate_native_keyword_localization'),
              mock.patch.object(flow.subprocess, 'run'),
              mock.patch.object(publish_github, 'public_files', return_value={'Mod/RDmod.json': manifest}),
              mock.patch.object(publish_github, 'publish', side_effect=RuntimeError('GitHub failed')),
              mock.patch.object(flow, 'upload') as upload,
              self.assertRaisesRegex(RuntimeError, 'GitHub failed')):
            flow.main()
        upload.assert_not_called()
        self.assertFalse((self.folder / '.workflow.lock').exists())

    def test_build_failure_never_uploads_and_releases_lock(self):
        manifest = self.root / 'Mod' / 'RDmod.json'
        manifest.parent.mkdir()
        manifest.write_text(json.dumps(self.manifest))
        with (mock.patch.object(flow, 'ROOT', self.root), mock.patch.object(flow, 'WORKSHOP', self.folder),
              mock.patch.object(sys, 'argv', ['upload_workshop.py', '--upload']),
              mock.patch.object(flow, 'validate_localization_json'),
              mock.patch.object(flow, 'validate_native_keyword_localization'),
              mock.patch.object(flow.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'build')),
              mock.patch.object(flow, 'upload') as upload,
              self.assertRaises(subprocess.CalledProcessError)):
            flow.main()
        upload.assert_not_called()
        self.assertFalse((self.folder / '.workflow.lock').exists())


if __name__ == '__main__':
    unittest.main()
