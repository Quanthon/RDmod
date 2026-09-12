"""Crop related card art into 256x256 status icons; leave unassociated statuses alone."""
from __future__ import annotations

import argparse
from collections import Counter
import io
from pathlib import Path
import sys

from PIL import Image, ImageOps

from status_art import POWER_TYPES, read_statuses, related_card
from sync_art_assets import IMAGE_SUFFIXES, SOURCES, aliases_for, apply_plan, choose_image, write_report
from sync_card_design import read_cards, read_shared_bytes


def crop_icon(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as source:
        icon = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGBA'), (256, 256),
                            method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        out = io.BytesIO()
        icon.save(out, format='PNG')
        return out.getvalue()


def plan_icons(workspace: Path, statuses: list[dict], cards: list[dict], cards_dir: Path,
               output_dir: Path, overwrite: bool = False) -> tuple[list[dict], dict[Path, bytes]]:
    files = sorted(p for p in cards_dir.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    existing = sorted(p for p in output_dir.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    aliases = aliases_for(workspace, 'cards')
    items, writes = [], {}
    for row in statuses:
        if row.get('稀有度') == '弃用' or not row.get('关联卡牌') or str(row['关联卡牌']).strip() in ('', '无', 'None'):
            continue
        key = row['key']
        item = {'kind': 'powers', 'key': key, 'name': row.get('名称'), 'status': 'problem', 'warnings': []}
        items.append(item)
        try:
            card = related_card(row['关联卡牌'], cards)
            item['cardKey'] = card['key']
            if card.get('稀有度') == '弃用':
                item.update(status='unchanged', warnings=['关联卡牌已弃用，跳过'])
                continue
            try:
                target = choose_image(existing, key, row.get('名称'), {POWER_TYPES.get(key, key)})
            except FileNotFoundError:
                target = output_dir / f'{key}.png'
            if not target.resolve().is_relative_to(workspace.resolve()):
                raise ValueError('输出路径超出项目目录')
            item['target'] = str(target)
            if target.exists() and not overwrite:
                item.update(status='unchanged', warnings=['已有成品，保留；可用 --overwrite 重新裁剪'])
                continue
            if target.suffix.lower() != '.png':
                raise ValueError('已有成品不是PNG；请先另存为PNG')
            source = choose_image(files, card['key'], card.get('名称'), aliases.get(card['key'], set()))
            item['source'] = str(source)
            data = crop_icon(source.read_bytes())
            item['size'] = [256, 256]
            changed = not target.exists() or target.read_bytes() != data
            item['status'] = 'update' if changed else 'unchanged'
            if changed:
                writes[target] = data
        except (OSError, ValueError, SyntaxError) as exc:
            item['problem'] = str(exc)
    counts = Counter(item.get('target') for item in items if item.get('target'))
    for item in items:
        if item.get('target') and counts[item['target']] > 1:
            item.update(status='problem', problem='成品同时匹配多个状态；请使用各自key命名')
            writes.pop(Path(item['target']), None)
    return items, writes


def main(argv=None) -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='保存图标；默认只检查')
    parser.add_argument('--overwrite', action='store_true', help='重新裁剪已有的关联卡牌图标，写入前备份')
    parser.add_argument('--workbook', type=Path, default=workspace / 'design/RD卡牌设计.xlsx')
    parser.add_argument('--cards-dir', type=Path, default=workspace / SOURCES['cards'])
    parser.add_argument('--output-dir', type=Path, default=workspace / SOURCES['powers'])
    parser.add_argument('--report-dir', type=Path, default=workspace / 'outputs/status-icon-generation')
    args = parser.parse_args(argv)
    report = {'mode': '已应用' if args.apply else '仅检查', 'items': [], 'unused': [], 'backup': None}
    code = 0
    try:
        workbook = read_shared_bytes(args.workbook)
        items, writes = plan_icons(workspace, read_statuses(workbook), read_cards(workbook),
                                  args.cards_dir, args.output_dir, args.overwrite)
        report['items'] = items
        code = 2 if any(item['status'] == 'problem' for item in items) else 0
        if args.apply:
            backup = apply_plan(writes, workspace, args.report_dir)
            report['backup'] = str(backup) if backup else None
    except Exception as exc:
        report.update(mode='执行失败', error=str(exc))
        code = 1
    write_report(report, args.report_dir)
    return code


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
