import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.sax.saxutils import escape

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_status_icons as gen
import status_art
import sync_art_assets as art


def png(size=(512, 256), color=(255, 0, 0, 100)):
    out = io.BytesIO()
    Image.new('RGBA', size, color).save(out, format='PNG')
    return out.getvalue()


class StatusArtTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cards = self.root/'cards'; self.cards.mkdir()
        self.output = self.root/'icons'
        self.rows = [{'key': 'ExamplePower', '名称': '状态', '关联卡牌': '旧名（Test1）'}]
        self.card_rows = [{'key': 'Test1', '名称': '新名', '稀有度': '普通'}]
        (self.cards/'新名.png').write_bytes(png())

    def plan(self, rows=None, overwrite=False):
        return gen.plan_icons(self.root, self.rows if rows is None else rows, self.card_rows,
                              self.cards, self.output, overwrite)

    def test_center_square_crop_retains_alpha_and_does_not_stretch(self):
        source = Image.new('RGBA', (512, 256), 'blue')
        source.paste((255, 0, 0, 100), (128, 0, 384, 256))
        out = io.BytesIO(); source.save(out, format='PNG')
        with Image.open(io.BytesIO(gen.crop_icon(out.getvalue()))) as result:
            self.assertEqual(result.size, (256, 256))
            self.assertEqual(result.getpixel((0, 0)), (255, 0, 0, 100))
            self.assertEqual(result.getpixel((255, 255)), (255, 0, 0, 100))

    def test_independent_and_deprecated_are_skipped(self):
        rows = [{'key': 'Charge', '关联卡牌': None}, {**self.rows[0], '稀有度': '弃用'}]
        self.assertEqual(self.plan(rows), ([], {}))
        self.card_rows[0]['稀有度'] = '弃用'
        self.assertFalse(self.plan()[1])

    def test_key_association_survives_card_rename_and_existing_art_is_preserved(self):
        items, writes = self.plan()
        self.assertEqual(items[0]['cardKey'], 'Test1')
        self.assertFalse(self.output.exists())
        art.apply_plan(writes, self.root, self.root/'reports')
        target = self.output/'ExamplePower.png'
        original = target.read_bytes()
        (self.cards/'新名.png').write_bytes(png(color='green'))
        self.assertFalse(self.plan()[1])
        _, writes = self.plan(overwrite=True)
        backup = art.apply_plan(writes, self.root, self.root/'reports')
        self.assertEqual((backup/'icons/ExamplePower.png').read_bytes(), original)
        self.assertFalse(self.plan(overwrite=True)[1])

    def test_missing_ambiguous_and_broken_card_art_are_reported(self):
        for value in ('Missing', '甲（Test1）、乙（Test2）'):
            self.assertEqual(self.plan([{**self.rows[0], '关联卡牌': value}])[0][0]['status'], 'problem')
        (self.cards/'sub').mkdir()
        (self.cards/'sub/新名.png').write_bytes(png())
        self.assertFalse(self.plan()[1])
        (self.cards/'Test1.png').write_bytes(b'broken')
        self.assertEqual(self.plan()[0][0]['status'], 'problem')

    def test_duplicate_status_target_is_not_overwritten(self):
        self.output.mkdir(); (self.output/'状态.png').write_bytes(png())
        rows = self.rows + [{**self.rows[0], 'key': 'OtherPower'}]
        items, writes = self.plan(rows, overwrite=True)
        self.assertFalse(writes)
        self.assertTrue(all(i['status'] == 'problem' for i in items))

    def test_power_profile_insert_and_existing_override_are_idempotent(self):
        original = b'public sealed class ExamplePower : ModPowerTemplate\r\n{\r\n    public int Value => 1;\r\n}\r\n'
        result = art.resource_source(original, 'powers', 'ExamplePower')
        self.assertEqual(result.count(b'PowerAssetProfile'), 1)
        self.assertEqual(result.count(b'images/powers/ExamplePower.png'), 2)
        self.assertIn(b'public int Value => 1;', result)
        self.assertEqual(art.resource_source(result, 'powers', 'ExamplePower'), result)
        with self.assertRaises(ValueError):
            art.resource_source(b'public override string IconPath => GetIcon();', 'powers', 'ExamplePower')

    def test_sheet_alias_connects_runtime_type_without_renaming(self):
        code = self.root/'Mod/Powers/FlightPower.cs'; code.parent.mkdir(parents=True)
        code.write_text('public sealed class FlightPower : ModPowerTemplate {}')
        (self.cards/'飞行.png').write_bytes(png())
        items, writes, _ = art.plan_group(self.root, 'powers', [{'key': 'Flying', '名称': '飞行'}], self.cards)
        self.assertEqual(items[0]['status'], 'update')
        self.assertIn(self.root/'Mod/RDMod/images/powers/FlightPower.png', writes)
        self.assertIn(b'class FlightPower', writes[code])

    def test_shared_source_keeps_both_power_profiles_and_second_run_has_no_writes(self):
        code = self.root/'Mod/Powers/Shared.cs'; code.parent.mkdir(parents=True)
        code.write_text('public sealed class OnePower : TypedHandRetainPower {}\n'
                        'public sealed class TwoPower : TypedHandRetainPower {}')
        for key in ('OnePower', 'TwoPower'):
            (self.cards/f'{key}.png').write_bytes(png())
        rows = [{'key': key} for key in ('OnePower', 'TwoPower')]
        items, writes, _ = art.plan_group(self.root, 'powers', rows, self.cards)
        self.assertTrue(all(item['status'] == 'update' for item in items))
        self.assertEqual(writes[code].count(b'images/powers/OnePower.png'), 2)
        self.assertEqual(writes[code].count(b'images/powers/TwoPower.png'), 2)
        art.apply_plan(writes, self.root, self.root/'reports')
        self.assertFalse(art.plan_group(self.root, 'powers', rows, self.cards)[1])

    def test_temporary_wrapper_gets_profile_and_namespace(self):
        source = b'public sealed class ApplePower : ModTemporaryAppliedPowerTemplate<Apple, StrengthPower> {}'
        result = art.resource_source(source, 'powers', 'ApplePower')
        self.assertIn(b'using STS2RitsuLib.Scaffolding.Content;', result)
        self.assertIn(b'ModTemporaryAppliedPowerTemplate<Apple, StrengthPower>', result)
        self.assertEqual(art.resource_source(result, 'powers', 'ApplePower'), result)

    def test_sheet_reader_handles_reordered_columns_and_rejects_collisions(self):
        def workbook(rows):
            data = io.BytesIO()
            xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            for n, row in enumerate(rows, 1):
                xml += '<row>' + ''.join(f'<c r="{chr(65+i)}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for i,v in enumerate(row)) + '</row>'
            xml += '</sheetData></worksheet>'
            with zipfile.ZipFile(data, 'w') as archive:
                archive.writestr('sheet.xml', xml)
            return data.getvalue()
        rows = [['名称', '关联卡牌', 'key'], ['飞行', '', 'Flying']]
        with patch.object(status_art, 'worksheet_entry', return_value='sheet.xml'):
            self.assertEqual(status_art.read_statuses(workbook(rows))[0]['key'], 'Flying')
            with self.assertRaises(ValueError):
                status_art.read_statuses(workbook(rows + [['重复', '', 'FlightPower']]))


if __name__ == '__main__':
    unittest.main()
