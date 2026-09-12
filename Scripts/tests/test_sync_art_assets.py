import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_art_assets as art
import card_design_apply


def png(color='red'):
    out = io.BytesIO(); Image.new('RGBA', (250, 190), color).save(out, format='PNG'); return out.getvalue()


def row(key='Test1', name='测试'):
    return {'key': key, '名称': name, '稀有度': '普通'}


class ArtSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'input'; self.source.mkdir()

    def card(self, key='Test1'):
        p = self.root/'Mod/Cards'/f'{key}.cs'; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('public override CardAssetProfile AssetProfile => new(PortraitPath: $"res://RDMod/images/cards/{GetType().Name}.png");')
        return p

    def plan(self, rows=None, aliases=None):
        return art.plan_group(self.root, 'cards', rows or [row()], self.source, aliases)

    def test_key_current_name_and_confirmed_alias_priority(self):
        for name in ('Test1', '新名', '旧名'):
            (self.source/f'{name}.png').write_bytes(png())
        files = list(self.source.iterdir())
        self.assertEqual(art.choose_image(files, 'Test1', '新名', {'旧名'}).stem, 'Test1')
        files = [p for p in files if p.stem != 'Test1']
        self.assertEqual(art.choose_image(files, 'Test1', '新名', {'旧名'}).stem, '新名')
        self.assertEqual(art.choose_image(files, 'Test1', '另一个新名', {'旧名'}).stem, '旧名')

    def test_ambiguous_duplicate_filenames_are_not_applied(self):
        self.card(); (self.source/'a').mkdir(); (self.source/'b').mkdir()
        for folder in ('a', 'b'): (self.source/folder/'测试.png').write_bytes(png())
        items, writes, _ = self.plan()
        self.assertEqual(items[0]['status'], 'problem'); self.assertFalse(writes)

    def test_plan_is_read_only_and_apply_is_idempotent_with_backup(self):
        code = self.card(); original_code = code.read_bytes()
        target = self.root/'Mod/RDMod/images/cards/Test1.png'; target.parent.mkdir(parents=True)
        target.write_bytes(png('blue')); old = target.read_bytes()
        (self.source/'测试.png').write_bytes(png())
        items, writes, _ = self.plan()
        self.assertEqual(target.read_bytes(), old); self.assertNotIn(code, writes)
        backup = art.apply_plan(writes, self.root, self.root/'reports')
        self.assertEqual((backup/target.relative_to(self.root)).read_bytes(), old)
        self.assertEqual(code.read_bytes(), original_code)
        self.assertEqual(target.read_bytes(), png())
        items, writes, _ = self.plan()
        self.assertEqual(items[0]['status'], 'unchanged'); self.assertFalse(writes)

    def test_relic_profile_connects_all_three_paths(self):
        code = self.root/'Mod/Relics/Test1.cs'; code.parent.mkdir(parents=True)
        code.write_text('[RegisterRelic(typeof(SharedRelicPool))]\npublic override RelicAssetProfile AssetProfile => new(IconPath: "res://old.png", IconOutlinePath: "res://outline.png", BigIconPath: "res://big.png");')
        (self.source/'测试.png').write_bytes(png())
        items, writes, _ = art.plan_group(self.root, 'relics', [row()], self.source)
        self.assertEqual(items[0]['status'], 'update')
        self.assertEqual(writes[code].count(b'res://RDMod/images/relics/Test1.png'), 1)
        self.assertIn(b'Test1_icon.png', writes[code])
        self.assertIn(b'Test1_outline.png', writes[code])
        art.apply_plan(writes, self.root, self.root/'reports')
        self.assertFalse(art.plan_group(self.root, 'relics', [row()], self.source)[1])
        self.assertIn(b'SharedRelicPool', writes[code])

    def test_outline_expands_alpha_and_preserves_edge_pixels(self):
        source = Image.new('RGBA', (5, 5), (255, 0, 0, 255))
        buffer = io.BytesIO(); source.save(buffer, format='PNG')
        icon_bytes, outline_bytes = art.relic_textures(buffer.getvalue())
        with Image.open(io.BytesIO(icon_bytes)) as icon, Image.open(io.BytesIO(outline_bytes)) as outline:
            self.assertEqual(icon.size, outline.size)
            self.assertEqual(icon.size, (9, 9))
            self.assertEqual(icon.crop((2, 2, 7, 7)).tobytes(), source.tobytes())
            self.assertEqual(outline.getpixel((1, 2)), (0, 0, 0, 255))
            self.assertEqual(icon.getpixel((1, 2))[3], 0)
            self.assertEqual(outline.getchannel('A').getbbox(), (1, 1, 8, 8))
            self.assertEqual(outline.getpixel((0, 0))[3], 0)

    def test_fully_transparent_relic_is_reported(self):
        source = Image.new('RGBA', (5, 5)); buffer = io.BytesIO(); source.save(buffer, format='PNG')
        with self.assertRaisesRegex(ValueError, '完全透明'):
            art.relic_textures(buffer.getvalue())

    def test_bad_images_report_problem_without_blocking_good_items(self):
        self.card(); self.card('Test2')
        (self.source/'测试.png').write_bytes(b'broken')
        (self.source/'Test2.png').write_bytes(png())
        items, writes, _ = self.plan([row(), row('Test2', '另一个')])
        self.assertEqual([i['status'] for i in items], ['problem', 'update'])
        self.assertEqual(len(writes), 1)

    def test_missing_unimplemented_and_deprecated(self):
        (self.source/'Test2.png').write_bytes(png()); (self.source/'Test3.png').write_bytes(png())
        items, writes, unused = self.plan([row(), row('Test2'), {**row('Test3'), '稀有度': '弃用'}])
        self.assertEqual(len(items), 2); self.assertFalse(writes); self.assertFalse(unused)
        self.assertTrue(all(i['status'] == 'problem' for i in items))

    def test_one_name_cannot_silently_supply_two_keys(self):
        self.card(); self.card('Test2'); (self.source/'测试.png').write_bytes(png())
        items, writes, _ = self.plan([row(), row('Test2')])
        self.assertFalse(writes); self.assertTrue(all(i['status'] == 'problem' for i in items))

    def test_unused_files_are_reported(self):
        self.card(); (self.source/'测试.png').write_bytes(png()); extra=self.source/'备选.png'; extra.write_bytes(png())
        self.assertEqual(self.plan()[2], [str(extra)])

    def test_unknown_dynamic_profile_is_not_overwritten(self):
        code=self.card(); code.write_text('public override CardAssetProfile AssetProfile => new(PortraitPath: GetPortrait());')
        (self.source/'测试.png').write_bytes(png())
        items, writes, _ = self.plan(); self.assertFalse(writes); self.assertEqual(items[0]['status'], 'problem')

    def test_confirmed_history_name_survives_snapshot_acceptance(self):
        snapshot = self.root/'design/card-design-snapshots/current.json'
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text(json.dumps({'cards': [{'key': 'Test1', '名称': '新名'}]}))
        history = snapshot.parent/'history'; history.mkdir()
        (history/'old.json').write_text(json.dumps({'cards': [{'key': 'Test1', '名称': '旧名'}]}))
        aliases = art.aliases_for(self.root, 'cards')
        self.assertEqual(aliases['Test1'], {'新名', '旧名'})
        self.card(); old = self.source/'旧名.png'; old.write_bytes(png())
        items, writes, _ = self.plan([row('Test1', '新名')], aliases)
        self.assertEqual(items[0]['source'], str(old)); self.assertTrue(writes)

    def test_aliases_include_localization_for_unnamed_old_snapshot(self):
        snap=self.root/'design/card-design-snapshots/current.json'; snap.parent.mkdir(parents=True)
        snap.write_text(json.dumps({'cards':[{'key':'Test1','名称':None}]}))
        loc=self.root/'Mod/RDMod/localization/zhs/cards.json'; loc.parent.mkdir(parents=True)
        loc.write_text(json.dumps({'RD_MOD_CARD_TEST1.title':'旧名'}))
        self.assertEqual(art.aliases_for(self.root, 'cards'), {'Test1':{'旧名'}})

    def test_atomic_write_failure_restores_original_files(self):
        a=self.root/'a.png'; b=self.root/'b.png'; a.write_bytes(b'a'); b.write_bytes(b'b')
        replace=card_design_apply.os.replace; calls=0
        def fail_second(src, dst):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('simulated replace failure')
            return replace(src, dst)
        with patch('card_design_apply.os.replace', side_effect=fail_second):
            with self.assertRaises(OSError): art.apply_plan({a:b'new a', b:b'new b'}, self.root, self.root/'reports')
        self.assertEqual(a.read_bytes(), b'a'); self.assertEqual(b.read_bytes(), b'b')

    def test_failed_export_can_retry_when_images_are_already_synced(self):
        self.card(); (self.source/'测试.png').write_bytes(png())
        report=self.root/'reports'
        args=['--apply','--kind','cards','--cards-dir',str(self.source),'--report-dir',str(report),'--export-pck']
        with patch.object(art, '__file__', str(self.root/'Scripts/sync_art_assets.py')), patch.object(art,'read_shared_bytes',return_value=b''), patch.object(art,'read_cards',return_value=[row()]), patch.object(art.subprocess,'run',side_effect=[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)]) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(art.main(args), 1); self.assertTrue((report/'pending-export').exists())
            self.assertEqual(art.main(args), 0); self.assertFalse((report/'pending-export').exists())
            self.assertEqual(run.call_count, 2)


if __name__ == '__main__': unittest.main()
