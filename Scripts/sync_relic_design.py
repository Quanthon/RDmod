"""Report relic-sheet changes; accept a baseline after manual implementation and validation."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sync_card_design import (
    NS, PASCAL_CASE, cell_value, column_index, read_shared_bytes,
    registration_id, shared_strings, worksheet_entry, xml_from_zip,
)

HEADERS = ['key', '名称', '遗物池', '稀有度', '描述', '备注']
RELIC_POOLS = {'RD': 'RainbowDashRelicPool', '通用': 'SharedRelicPool'}


def validate_rows(rows):
    seen = set()
    normalized = []
    for row in rows:
        key = row.get('key')
        if not isinstance(key, str) or not PASCAL_CASE.fullmatch(key):
            raise ValueError(f'Invalid PascalCase relic key: {key!r}')
        if key in seen:
            raise ValueError(f'Duplicate relic key: {key}')
        seen.add(key)
        # Legacy snapshots predate the pool column; every relic used the RD pool.
        pool = row.get('遗物池', 'RD')
        if pool not in RELIC_POOLS:
            raise ValueError(f'{key}: 遗物池 must be RD or 通用; got {pool!r}')
        normalized.append({**row, '遗物池': pool})
    return sorted(normalized, key=lambda row: row['key'])


def read_relics(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        strings = shared_strings(archive)
        sheet = xml_from_zip(archive, worksheet_entry(archive, '遗物'))
        matrix = []
        for row in sheet.findall('.//x:sheetData/x:row', NS):
            values = [None] * len(HEADERS)
            for cell in row.findall('x:c', NS):
                index = column_index(cell.get('r') or '')
                if 0 <= index < len(values):
                    values[index] = cell_value(cell, strings)
            if any(value is not None and value != '' for value in values):
                matrix.append(values)
    if not matrix or matrix[0] != HEADERS:
        raise ValueError(f'Expected relic headers: {HEADERS}')
    return validate_rows([dict(zip(HEADERS, row, strict=True)) for row in matrix[1:]])


def compare(previous, current, selected):
    old = {row['key']: row for row in validate_rows(previous)}
    new = {row['key']: row for row in validate_rows(current)}
    unknown = selected - (old.keys() | new.keys())
    if unknown:
        raise ValueError(f'Unknown relic keys: {sorted(unknown)}')
    changes = []
    for key in sorted(selected or (old.keys() | new.keys())):
        before, after = old.get(key), new.get(key)
        if before == after:
            continue
        changes.append({'key': key, 'kind': 'added' if before is None else 'removed' if after is None else 'changed',
                        'before': before, 'after': after})
    return changes


def accepted_rows(previous, current, selected):
    # Deletions are reported and kept pending until their compatibility is handled separately.
    changes = compare(previous, current, selected)
    if any(change['kind'] == 'removed' for change in changes):
        raise ValueError('Removed relics require separate compatibility review; accept other keys individually.')
    rows = {row['key']: row for row in previous}
    rows.update({row['key']: row for row in current if not selected or row['key'] in selected})
    return validate_rows(list(rows.values()))


def check_implementation(workspace, rows):
    localization = json.loads((workspace / 'Mod/RDMod/localization/zhs/relics.json').read_text(encoding='utf-8-sig'))
    for row in validate_rows(rows):
        key = row['key']
        source = (workspace / 'Mod/Relics' / f'{key}.cs').read_text(encoding='utf-8-sig')
        expected_pool = RELIC_POOLS[row['遗物池']]
        registered_pools = re.findall(r'\[RegisterRelic\(typeof\((\w+)\)\)\]', source)
        if registered_pools != [expected_pool]:
            raise ValueError(f'{key}: register in {expected_pool} before acceptance')
        prefix = registration_id(key).replace('RD_MOD_CARD_', 'RD_MOD_RELIC_', 1)
        for suffix in ('title', 'description'):
            if not localization.get(f'{prefix}.{suffix}'):
                raise ValueError(f'{key}: missing relic localization {suffix}')


def main():
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=workspace / 'design/RD卡牌设计.xlsx')
    parser.add_argument('--snapshot', type=Path, default=workspace / 'design/relic-design-snapshots/current.json')
    parser.add_argument('--key', action='append', default=[])
    parser.add_argument('--accept', action='store_true')
    args = parser.parse_args()
    current = read_relics(read_shared_bytes(args.workbook))
    previous = []
    if args.snapshot.exists():
        payload = json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
        if payload.get('schemaVersion') != 1 or payload.get('sheet') != '遗物':
            raise ValueError('Unsupported relic snapshot')
        previous = validate_rows(payload['relics'])
    else:
        print('RELIC_BASELINE_MISSING: all rows are pending initial verification, not necessarily new content.')
    selected = set(args.key)
    changes = compare(previous, current, selected)
    print('RELIC_DESIGN_DIFF ' + ' '.join(f'{kind}={sum(c["kind"] == kind for c in changes)}' for kind in ('added', 'removed', 'changed')))
    for change in changes:
        print(json.dumps(change, ensure_ascii=False))
    if args.accept and changes:
        rows = accepted_rows(previous, current, selected)
        check_implementation(workspace, [row for row in rows if not selected or row['key'] in selected])
        payload = {'schemaVersion': 1, 'sheet': '遗物', 'capturedAtUtc': datetime.now(timezone.utc).isoformat(), 'relics': rows}
        content = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
        history = args.snapshot.parent / 'history'
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        (history / f'{stamp}.json').write_text(content, encoding='utf-8')
        temporary = args.snapshot.with_suffix('.tmp')
        temporary.write_text(content, encoding='utf-8')
        os.replace(temporary, args.snapshot)
        print(f'RELIC_DESIGN_SNAPSHOT_ACCEPTED relics={len(rows)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
