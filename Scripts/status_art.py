"""Read the status sheet and resolve its existing runtime type names."""
from __future__ import annotations

import io
import re
import zipfile

from sync_card_design import (
    NS, PASCAL_CASE, cell_value, column_index, shared_strings,
    worksheet_entry, xml_from_zip,
)

POWER_TYPES = {'Flying': 'FlightPower', 'Charge': 'PreparationPower', 'OverSpeed': 'OverdrivePower'}


def read_statuses(data: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        strings = shared_strings(archive)
        sheet = xml_from_zip(archive, worksheet_entry(archive, '状态'))
        matrix = []
        for row in sheet.findall('.//x:sheetData/x:row', NS):
            values = {}
            for cell in row.findall('x:c', NS):
                values[column_index(cell.get('r') or '')] = cell_value(cell, strings)
            if any(v not in (None, '') for v in values.values()):
                matrix.append(values)
    if not matrix:
        raise ValueError('状态表为空')
    headers = matrix[0]
    for field in ('key', '名称', '关联卡牌'):
        if list(headers.values()).count(field) != 1:
            raise ValueError(f'状态表缺少唯一列：{field}')
    rows, seen = [], set()
    for values in matrix[1:]:
        row = {field: values.get(index) for index, field in headers.items() if field}
        key = row.get('key')
        if not isinstance(key, str) or not PASCAL_CASE.fullmatch(key):
            raise ValueError(f'状态 key 必须为 PascalCase：{key!r}')
        runtime = POWER_TYPES.get(key, key)
        if runtime.casefold() in seen:
            raise ValueError(f'状态 key 或对应能力类型重复：{key}')
        seen.add(runtime.casefold())
        rows.append(row)
    return rows


def related_card(value: str, cards: list[dict]) -> dict:
    """Accept a stable key, an exact current name, or the sheet's 名称（Key） form."""
    label = str(value).strip()
    match = re.fullmatch(r'[^（）()]*[（(]([A-Z][A-Za-z0-9]*)[）)]', label)
    key = match.group(1) if match else label
    matches = [card for card in cards if card['key'] == key]
    if not matches and not match:
        matches = [card for card in cards if card.get('名称') == label]
    if len(matches) != 1:
        raise ValueError(f'关联卡牌无法唯一匹配：{value}')
    return matches[0]
