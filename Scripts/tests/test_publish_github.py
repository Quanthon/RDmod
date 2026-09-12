import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_github as github


class GitHubPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'workshop'
        (self.folder / 'media').mkdir(parents=True)
        (self.root / 'Mod').mkdir()
        self.gh = self.root / 'gh.exe'
        self.gh.touch()
        (self.folder / 'settings.json').write_text(json.dumps({'description_file':'description.txt','github':{'repository':'Quanthon/RDmod','cli':str(self.gh)}}))
        (self.folder / 'description.txt').write_text('[img]media/demo.gif[/img]')
        from PIL import Image
        Image.new('RGB', (2, 2)).save(self.folder / 'media/demo.gif')
        (self.root / 'README.md').write_text('Public README')
        (self.root / 'LICENSE').write_text('MIT')
        (self.root / 'Mod/RDmod.csproj').write_text('<Project/>')
        (self.root / 'Mod/RDmod.json').write_text('{"version":"1.0.0"}')

    def test_media_and_gif_reference(self):
        files = github.media_files(self.folder, '[img]media/demo.gif[/img]')
        self.assertEqual(list(files), ['media/demo.gif'])
        text = github.render_description('[img]media/中文 图片.png[/img]', 'Quanthon/RDmod', 'abc123')
        self.assertEqual(text, '[img]https://raw.githubusercontent.com/Quanthon/RDmod/abc123/workshop/media/%E4%B8%AD%E6%96%87%20%E5%9B%BE%E7%89%87.png[/img]')
        self.assertEqual(github.render_description('[img]https://example.org/x.png[/img]', 'Quanthon/RDmod', 'abc'), '[img]https://example.org/x.png[/img]')

    def test_media_escape_and_non_image_rejected(self):
        for name in ('media/../settings.json','media/../../outside.png','media/file.exe'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                github.media_files(self.folder, '[img]' + name + '[/img]')

    def test_public_snapshot_excludes_private_files_and_generated_binaries(self):
        for name in ('design/private.xlsx','OfficialReference/source.cs','.tools/secret.json',
                     'Mod/.godot/cache.cs','Mod/.vscode/settings.json','Mod/secret.env','Mod/output.dll',
                     'workshop/mod_id.txt','workshop/logs/error.log','workshop/media/unreferenced.png'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('private')
        files = github.public_files(self.root)
        self.assertIn('Mod/RDmod.csproj', files)
        self.assertIn('workshop/media/demo.gif', files)
        self.assertFalse(any('private' in key or '.godot' in key or 'OfficialReference' in key or '.tools' in key or 'mod_id' in key or 'unreferenced' in key for key in files))
        self.assertNotIn('Mod/output.dll', files)
        self.assertNotIn('Mod/secret.env', files)

    def test_wrong_account_stops_before_repo_creation(self):
        completed = subprocess.CompletedProcess([], 0, 'another-account\n', '')
        with mock.patch.object(github, 'run', return_value=completed) as run, self.assertRaises(RuntimeError):
            github.publish(self.root, {}, self.root / 'release.zip')
        self.assertEqual(run.call_count, 1)

    def test_private_repo_is_not_automatically_made_public(self):
        results = [subprocess.CompletedProcess([],0,'Quanthon\n',''),
                   subprocess.CompletedProcess([],0,json.dumps({'private':True,'default_branch':'main'}),'')]
        with mock.patch.object(github, 'run', side_effect=results) as run, self.assertRaises(ValueError):
            github.publish(self.root, {}, self.root / 'release.zip')
        self.assertEqual(run.call_count, 2)

    def test_network_error_does_not_create_repo(self):
        results = [subprocess.CompletedProcess([],0,'Quanthon\n',''),
                   subprocess.CompletedProcess([],1,'','network error')]
        with mock.patch.object(github, 'run', side_effect=results) as run, self.assertRaises(RuntimeError):
            github.publish(self.root, {}, self.root / 'release.zip')
        self.assertEqual(run.call_count, 2)

    def test_raw_url_is_checked_without_credentials(self):
        source = self.folder / 'media/demo.gif'
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = source.read_bytes()
        with mock.patch.object(github.urllib.request, 'urlopen', return_value=response) as opened:
            github.verify_raw('https://raw.githubusercontent.com/Quanthon/RDmod/sha/demo.gif', source)
        self.assertIsInstance(opened.call_args.args[0], str)
        self.assertNotIn('headers', opened.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
