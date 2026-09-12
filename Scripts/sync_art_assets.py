"""Synchronize card portraits, relic icons and status icons from the design workbook's image folders."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageFilter

from card_design_apply import atomic_write_group
from sync_card_design import read_cards, read_shared_bytes, registration_id
from sync_relic_design import read_relics
from status_art import POWER_TYPES, read_statuses

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
SOURCES = {'cards': '截图/卡牌/裁剪后', 'relics': '截图/遗物/裁剪后', 'powers': '截图/状态/成品'}


def resource_source(source: bytes, kind: str, key: str) -> bytes:
    if kind != 'powers':
        return _resource_source(source, kind, key)
    text = source.decode('utf-8-sig')
    # Mask comments and literals so their braces cannot end a class early.
    masked = re.sub(r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"',
                    lambda m: ' ' * len(m.group()), text, flags=re.S)
    matches = list(re.finditer(rf'public sealed class {re.escape(key)}\s*:[^{{]+\{{', masked))
    if len(matches) != 1:
        raise ValueError('无法唯一识别能力类型声明；请人工接入资源路径')
    match = matches[0]
    depth, end = 1, match.end()
    while end < len(masked) and depth:
        depth += (masked[end] == '{') - (masked[end] == '}')
        end += 1
    if depth:
        raise ValueError('能力类型括号不完整')
    body = _resource_source(text[match.start():end].encode('utf-8'), kind, key).decode('utf-8')
    result = text[:match.start()] + body + text[end:]
    if result == text:
        return source
    if 'using STS2RitsuLib.Scaffolding.Content;' not in result:
        newline = '\r\n' if '\r\n' in result else '\n'
        result = 'using STS2RitsuLib.Scaffolding.Content;' + newline + result
    return (b'\xef\xbb\xbf' if source.startswith(b'\xef\xbb\xbf') else b'') + result.encode('utf-8')


def _resource_source(source: bytes, kind: str, key: str) -> bytes:
    """Connect only recognized asset-profile literals, preserving unrelated C# code."""
    text = source.decode('utf-8-sig')
    profile = {'cards': 'CardAssetProfile', 'relics': 'RelicAssetProfile', 'powers': 'PowerAssetProfile'}[kind]
    if kind == 'powers' and not re.search(r'\b(?:AssetProfile|IconPath|BigIconPath)\b', text):
        declaration = re.search(rf'(public sealed class {re.escape(key)}\s*:\s*(?:ModPowerTemplate|TypedHandRetainPower|ModTemporaryAppliedPowerTemplate<\w+,\s*\w+>)\s*\{{)', text)
        if not declaration:
            raise ValueError('无法识别能力类型声明；请人工接入资源路径')
        newline = '\r\n' if '\r\n' in text else '\n'
        addition = newline + newline + newline.join([
            '    public override PowerAssetProfile AssetProfile => new(',
            f'        IconPath: "res://RDMod/images/powers/{key}.png",',
            f'        BigIconPath: "res://RDMod/images/powers/{key}.png");',
        ])
        text = text[:declaration.end()] + addition + text[declaration.end():]
    match = re.search(rf'{profile}\s+AssetProfile\s*=>\s*new\((.*?)\);', text, re.S)
    if not match:
        raise ValueError('无法识别 AssetProfile；请人工接入资源路径')
    body = match.group(1)
    fields = {'cards': ('PortraitPath',), 'relics': ('IconPath', 'IconOutlinePath', 'BigIconPath'),
              'powers': ('IconPath', 'BigIconPath')}[kind]
    for field in fields:
        suffix = {'IconPath': '_icon', 'IconOutlinePath': '_outline'}.get(field, '') if kind == 'relics' else ''
        target = f'res://RDMod/images/{kind}/{key}{suffix}.png'
        pattern = rf'(\b{field}\s*:\s*)(\$?"[^"\r\n]*")'
        hits = list(re.finditer(pattern, body))
        if len(hits) != 1:
            raise ValueError(f'无法唯一识别 {field}；请人工接入资源路径')
        value = hits[0].group(2)
        if value == f'"{target}"' or value == f'$"res://RDMod/images/{kind}/{{GetType().Name}}.png"':
            continue
        # An interpolated custom expression is not safe to replace automatically.
        if value.startswith('$'):
            raise ValueError(f'{field} 使用自定义动态路径；请人工确认')
        body = re.sub(pattern, lambda m: m.group(1) + f'"{target}"', body, count=1)
    result = text[:match.start(1)] + body + text[match.end(1):]
    if result == source.decode('utf-8-sig'):
        return source
    return (b'\xef\xbb\xbf' if source.startswith(b'\xef\xbb\xbf') else b'') + result.encode('utf-8')


def relic_textures(data: bytes) -> tuple[bytes, bytes]:
    """Derive aligned display/outline textures; retain the source as the large icon."""
    with Image.open(io.BytesIO(data)) as source:
        rgba = source.convert('RGBA')
    if rgba.getchannel('A').getextrema()[1] == 0:
        raise ValueError('遗物图标完全透明，无法生成轮廓')
    # Approximately two outline pixels at the game's 85px small-icon size.
    radius = max(1, round(min(rgba.size) * 2 / 85))
    padding = radius + 1
    icon = Image.new('RGBA', (rgba.width + 2 * padding, rgba.height + 2 * padding))
    icon.paste(rgba, (padding, padding))
    alpha = icon.getchannel('A').filter(ImageFilter.MaxFilter(2 * radius + 1))
    outline = Image.new('RGBA', icon.size, (0, 0, 0, 0))
    outline.putalpha(alpha)
    outputs = []
    for image in (icon, outline):
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        outputs.append(buffer.getvalue())
    return outputs[0], outputs[1]


def aliases_for(workspace: Path, kind: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if kind == 'powers':
        return {key: {runtime} for key, runtime in POWER_TYPES.items()}
    snapshot = workspace / 'design' / f'{"card" if kind == "cards" else "relic"}-design-snapshots/current.json'
    snapshots = ([snapshot] if snapshot.exists() else []) + sorted((snapshot.parent / 'history').glob('*.json'))
    for saved in snapshots:
        for row in json.loads(saved.read_text(encoding='utf-8-sig')).get(kind, []):
            result.setdefault(row['key'], set())
            if row.get('名称'):
                result[row['key']].add(row['名称'])
    localization = workspace / f'Mod/RDMod/localization/zhs/{kind}.json'
    if localization.exists():
        # ID-to-name association is authoritative; fuzzy filename matching is intentionally absent.
        names = json.loads(localization.read_text(encoding='utf-8-sig'))
        for key in result:
            prefix = registration_id(key)
            if kind == 'relics':
                prefix = prefix.replace('RD_MOD_CARD_', 'RD_MOD_RELIC_', 1)
            if names.get(prefix + '.title'):
                result[key].add(names[prefix + '.title'])
    return result


def choose_image(files: list[Path], key: str, name: str | None, aliases: set[str]) -> Path:
    for labels in ({key}, {name} if name else set(), aliases - {name, key}):
        normalized = {label.casefold() for label in labels}
        matches = [p for p in files if p.stem.casefold() in normalized]
        if len(matches) > 1:
            raise ValueError('同一匹配级别存在多个图片：' + '、'.join(str(p) for p in matches))
        if matches:
            return matches[0]
    raise FileNotFoundError('没有找到对应图片')


def plan_group(workspace: Path, kind: str, rows: list[dict], source_dir: Path,
               aliases: dict[str, set[str]] | None = None) -> tuple[list[dict], dict[Path, bytes], list[str]]:
    aliases = aliases or {}
    files = sorted(p for p in source_dir.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) if source_dir.is_dir() else []
    items = []
    used = set()
    ignored_labels = set()
    for row in rows:
        key, name = row['key'], row.get('名称')
        if row.get('稀有度') == '弃用':
            ignored_labels.update(str(x).casefold() for x in (key, name) if x)
            continue
        item = {'kind': kind, 'key': key, 'name': name, 'status': 'problem', 'warnings': []}
        items.append(item)
        try:
            if not source_dir.is_dir():
                raise FileNotFoundError(f'来源文件夹不存在：{source_dir}')
            image = choose_image(files, key, name, aliases.get(key, set()))
            item['source'] = str(image)
            used.add(image)
            if image.suffix.lower() != '.png':
                raise ValueError('目前仅同步PNG；请将该图片另存为PNG')
            data = image.read_bytes()
            with Image.open(io.BytesIO(data)) as decoded:
                if decoded.format != 'PNG':
                    raise ValueError('扩展名为PNG，但实际格式不是PNG')
                width, height = decoded.size
                decoded.verify()
            item['size'] = [width, height]
            if kind == 'cards':
                expected = 250 / 351 if row.get('稀有度') == '先古' else 250 / 190
                if abs(width / height - expected) > 0.02:
                    item['warnings'].append('卡图宽高比与常用比例不同；保留原图，不自动裁剪')
            elif width != height:
                item['warnings'].append('图标不是正方形；保留原图，不自动裁剪')
            runtime_key = POWER_TYPES.get(key, key) if kind == 'powers' else key
            code = workspace / 'Mod' / {'cards': 'Cards', 'relics': 'Relics', 'powers': 'Powers'}[kind] / f'{runtime_key}.cs'
            if kind == 'powers' and not code.is_file():
                matches = [p for p in (workspace / 'Mod/Powers').glob('*.cs')
                           if re.search(rf'public sealed class {re.escape(runtime_key)}\s*:', p.read_text(encoding='utf-8-sig'))]
                if len(matches) > 1:
                    raise ValueError('多个文件声明同一能力类型')
                if matches:
                    code = matches[0]
            if not code.is_file():
                raise FileNotFoundError('尚未实现对应C#类型；图片保留在来源目录')
            target = workspace / f'Mod/RDMod/images/{kind}/{runtime_key}.png'
            for path in (code, target):
                if not path.resolve().is_relative_to(workspace.resolve()):
                    raise ValueError('目标路径超出项目目录')
            patched_code = resource_source(code.read_bytes(), kind, runtime_key)
            candidates = {target: data, code: patched_code}
            if kind == 'relics':
                icon, outline = relic_textures(data)
                icon_path = target.with_name(f'{key}_icon.png')
                outline_path = target.with_name(f'{key}_outline.png')
                candidates.update({icon_path: icon, outline_path: outline})
                item['icon'] = str(icon_path)
                item['outline'] = str(outline_path)
            for path in candidates:
                if not path.resolve().is_relative_to(workspace.resolve()):
                    raise ValueError('目标路径超出项目目录')
            writes = {p: b for p, b in candidates.items() if not p.exists() or p.read_bytes() != b}
            item['target'] = str(target)
            item['status'] = 'update' if writes else 'unchanged'
            item['_writes'] = writes
        except (OSError, ValueError, SyntaxError) as exc:
            item['problem'] = str(exc)
    counts = Counter(i.get('source') for i in items if i.get('source'))
    writes = {}
    for item in items:
        if item.get('source') and counts[item['source']] > 1:
            item['status'] = 'problem'
            item['problem'] = '该图片同时匹配多个key；请使用各自key命名图片以区分'
        pending = item.pop('_writes', {})
        if item['status'] != 'problem':
            for path, data in pending.items():
                if kind == 'powers' and path.suffix == '.cs' and path in writes:
                    data = resource_source(writes[path], kind, POWER_TYPES.get(item['key'], item['key']))
                writes[path] = data
    unused = [str(p) for p in files if p not in used and p.stem.casefold() not in ignored_labels]
    return items, writes, unused


def apply_plan(writes: dict[Path, bytes], workspace: Path, report_dir: Path) -> Path | None:
    if not writes:
        return None
    backup = report_dir / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    manifest = []
    for path in writes:
        relative = path.relative_to(workspace)
        existed = path.exists()
        if existed:
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        manifest.append({'path': str(relative), 'previouslyExisted': existed})
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    atomic_write_group(writes)
    return backup


def write_report(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    counts = Counter(i['status'] for i in report['items'])
    lines = [f'图片同步报告：{report["mode"]}', f'处理 {len(report["items"])} 项；更新 {counts["update"]}；不变 {counts["unchanged"]}；问题 {counts["problem"]}']
    for item in report['items']:
        if item['status'] != 'unchanged' or item['warnings']:
            lines.append(f'[{item["status"]}] {item["kind"]}/{item["key"]} {item.get("name") or ""}: ' + item.get('problem', item.get('source', '')))
            lines.extend('  提示：' + warning for warning in item['warnings'])
    lines += ['[多余文件] ' + path for path in report['unused']]
    if report.get('backup'):
        lines.append('备份：' + report['backup'])
    if report.get('error'):
        lines.append('执行错误：' + report['error'])
    lines.append('构建导出：' + report.get('export', '未请求'))
    (directory / 'latest.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print(f'完整报告：{directory / "latest.txt"}')


def main(argv=None) -> int:
    workspace = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='应用有效匹配；默认只检查')
    parser.add_argument('--kind', choices=('all', 'cards', 'relics', 'powers'), default='all')
    parser.add_argument('--cards-dir', type=Path, default=workspace / SOURCES['cards'])
    parser.add_argument('--relics-dir', type=Path, default=workspace / SOURCES['relics'])
    parser.add_argument('--powers-dir', type=Path, default=workspace / SOURCES['powers'])
    parser.add_argument('--workbook', type=Path, default=workspace / 'design/RD卡牌设计.xlsx')
    parser.add_argument('--report-dir', type=Path, default=workspace / 'outputs/art-sync')
    parser.add_argument('--export-pck', action='store_true', help='同步后构建并导出安装到游戏，不自动启动游戏')
    args = parser.parse_args(argv)
    if args.export_pck and not args.apply:
        parser.error('--export-pck requires --apply')
    report = {'mode': '已应用' if args.apply else '仅检查', 'items': [], 'unused': [], 'backup': None}
    code = 0
    try:
        workbook = read_shared_bytes(args.workbook)
        writes = {}
        for kind, reader, directory in [('cards', read_cards, args.cards_dir), ('relics', read_relics, args.relics_dir),
                                        ('powers', read_statuses, args.powers_dir)]:
            if args.kind not in ('all', kind):
                continue
            items, changes, unused = plan_group(workspace, kind, reader(workbook), directory, aliases_for(workspace, kind))
            report['items'].extend(items)
            report['unused'].extend(unused)
            writes.update(changes)
        if any(i['status'] == 'problem' for i in report['items']):
            code = 2
        if args.apply:
            backup = apply_plan(writes, workspace, args.report_dir)
            report['backup'] = str(backup) if backup else None
            pending = args.report_dir / 'pending-export'
            if writes:
                pending.parent.mkdir(parents=True, exist_ok=True)
                pending.touch()
            if args.export_pck:
                if pending.exists():
                    log = args.report_dir / 'last-export.log'
                    print(f'正在构建并导出资源，日志：{log}', flush=True)
                    with log.open('w', encoding='utf-8') as output:
                        result = subprocess.run([sys.executable, str(workspace / 'Scripts/debug_after_code.py'), '--export-pck', '--skip-launch'], cwd=workspace, stdout=output, stderr=subprocess.STDOUT, check=False)
                    if result.returncode:
                        report['export'] = f'失败，保留待导出状态，下次可重试；见 {log}'
                        code = 1
                    else:
                        report['export'] = '通过，已安装到游戏目录'
                        pending.unlink()
                else:
                    report['export'] = '无资源变化，无需重复导出'
            elif pending.exists():
                report['export'] = '待导出：运行 --apply --export-pck'
    except Exception as exc:
        report['error'] = str(exc)
        report['mode'] = '执行失败'
        code = 1
    write_report(report, args.report_dir)
    return code


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
