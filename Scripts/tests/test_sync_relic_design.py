import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sync_relic_design import HEADERS, accepted_rows, check_implementation, compare, read_relics


def relic(key, description='获得1点格挡。'):
    return dict(zip(HEADERS, [key, key, 'RD', '普通', description, None]))


def workbook(rows):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="遗物" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        contents = []
        for n, row in enumerate(rows, 1):
            cells = ''.join(f'<c r="{chr(65+i)}{n}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for i, value in enumerate(row) if value is not None)
            contents.append(f'<row r="{n}">{cells}</row>')
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(contents)+'</sheetData></worksheet>')
    return output.getvalue()


class RelicSyncTests(unittest.TestCase):
    def test_sheet_read_and_validation(self):
        row = relic('Test1')
        self.assertEqual(read_relics(workbook([HEADERS, list(row.values())])), [row])
        for rows in [[HEADERS, list(row.values()), list(row.values())], [HEADERS, [None,'遗漏key']], [['错误列']]]:
            with self.assertRaises(ValueError):
                read_relics(workbook(rows))

    def test_pool_column_is_read_without_shifting_fields(self):
        row = relic('Test7', '七选一'); row['遗物池'] = '通用'; row['备注'] = '允许跳过'
        self.assertEqual(read_relics(workbook([HEADERS, list(row.values())])), [row])

    def test_invalid_or_blank_pool_is_rejected(self):
        for pool in (None, '', '不存在的池'):
            row = relic('Test1'); row['遗物池'] = pool
            with self.subTest(pool=pool), self.assertRaises(ValueError):
                read_relics(workbook([HEADERS, list(row.values())]))

    def test_legacy_snapshot_defaults_to_rd_and_detects_pool_change(self):
        old = relic('Test1'); del old['遗物池']
        self.assertEqual(compare([old], [relic('Test1')], set()), [])
        new = relic('Test1'); new['遗物池'] = '通用'
        change = compare([old], [new], set())[0]
        self.assertEqual(change['before']['遗物池'], 'RD')
        self.assertEqual(change['after']['遗物池'], '通用')
        self.assertNotIn('遗物池', old)

    def test_acceptance_validates_selected_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'Mod/Relics/Test1.cs'; source.parent.mkdir(parents=True)
            loc = root/'Mod/RDMod/localization/zhs/relics.json'; loc.parent.mkdir(parents=True)
            loc.write_text(json.dumps({'RD_MOD_RELIC_TEST1.title': '测试', 'RD_MOD_RELIC_TEST1.description': '说明'}))
            row = relic('Test1'); row['遗物池'] = '通用'
            source.write_text('[RegisterRelic(typeof(RainbowDashRelicPool))]')
            with self.assertRaises(ValueError): check_implementation(root, [row])
            source.write_text('[RegisterRelic(typeof(SharedRelicPool))]')
            check_implementation(root, [row])
            with self.assertRaises(ValueError): check_implementation(root, [relic('Test1')])
            source.write_text('[RegisterRelic(typeof(SharedRelicPool))] [RegisterRelic(typeof(RainbowDashRelicPool))]')
            with self.assertRaises(ValueError): check_implementation(root, [row])

    def test_difference_includes_notes_and_deletion(self):
        updated = relic('Test1'); updated['备注'] = '新的触发条件'
        result = compare([relic('Test1'), relic('Test2')], [updated, relic('Test3')], set())
        self.assertEqual([r['kind'] for r in result], ['changed', 'removed', 'added'])
        self.assertEqual(result[0]['after']['备注'], '新的触发条件')

    def test_partial_accept_does_not_swallow_other_changes(self):
        old = [relic('Test1'), relic('Test2')]
        new = [relic('Test1','新描述'), relic('Test2','未实现'), relic('Test3')]
        self.assertEqual(accepted_rows(old,new,{'Test1'}),[new[0],old[1]])

    def test_unknown_and_removed_cannot_be_accepted(self):
        with self.assertRaises(ValueError): accepted_rows([],[],{'Missing'})
        with self.assertRaises(ValueError): accepted_rows([relic('Test1')],[],set())

    def test_missing_baseline_remains_pending(self):
        self.assertEqual(compare([], [relic('Test1')], set())[0]['kind'], 'added')
        self.assertEqual(accepted_rows([], [relic('Test1'),relic('Test2')], {'Test1'}),[relic('Test1')])

    def test_acceptance_requires_character_pool_and_localization(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'Mod/Relics/Test1.cs'; source.parent.mkdir(parents=True)
            loc=root/'Mod/RDMod/localization/zhs/relics.json'; loc.parent.mkdir(parents=True)
            loc.write_text(json.dumps({'RD_MOD_RELIC_TEST1.title':'测试','RD_MOD_RELIC_TEST1.description':'说明'}))
            source.write_text('[RegisterRelic(typeof(ColorlessRelicPool))]')
            with self.assertRaises(ValueError): check_implementation(root,[relic('Test1')])
            source.write_text('[RegisterRelic(typeof(RainbowDashRelicPool))]')
            check_implementation(root,[relic('Test1')])
            loc.write_text('{}')
            with self.assertRaises(ValueError): check_implementation(root,[relic('Test1')])


if __name__ == '__main__': unittest.main()
