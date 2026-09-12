#!/usr/bin/env python3
"""Prepare and upload RDmod using the official Mega Crit uploader."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
import zipfile
from pathlib import Path

from package_local_release import read_json, validate_archive_entries, validate_release_version, sha256
from release_validation import validate_localization_json, validate_native_keyword_localization

ROOT = Path(__file__).resolve().parent.parent
WORKSHOP = ROOT / 'workshop'
RITSULIB_ID = 3747602295


def write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)


def read_item_id(folder: Path) -> str | None:
    primary, backup = folder / 'mod_id.txt', folder / 'mod_id.backup.txt'
    values = []
    for path in (primary, backup):
        if path.exists():
            value = path.read_text(encoding='utf-8-sig').strip()
            if not re.fullmatch(r'[1-9][0-9]*', value) or int(value) >= 2**64:
                raise ValueError(f'无效工坊 ID：{path}')
            values.append(value)
    if len(set(values)) > 1:
        raise ValueError('mod_id.txt 与备份不一致，请确认正确工坊条目后统一两份 ID。')
    return values[0] if values else None


def save_item_id(folder: Path, value: str) -> None:
    old = read_item_id(folder)
    if old and old != value:
        raise ValueError(f'上传器返回不同工坊 ID：原 {old}，返回 {value}。请查看日志。')
    for name in ('mod_id.txt', 'mod_id.backup.txt'):
        write_text(folder / name, value + '\n')


def load_metadata(folder: Path) -> tuple[dict, Path]:
    settings = read_json(folder / 'settings.json')
    metadata = read_json(folder / 'workshop.json')
    allowed = {'title', 'description', 'visibility', 'changeNote', 'tags', 'dependencies',
               'contentDescriptors', 'minBranch', 'maxBranch'}
    if set(metadata) - allowed:
        raise ValueError(f'未知工坊配置字段：{sorted(set(metadata) - allowed)}')
    if metadata.get('visibility') not in {None, 'private', 'public', 'unlisted', 'friends_only'}:
        raise ValueError('visibility 使用 private、public、unlisted、friends_only 或 null。')
    for setting, field in [('description_file', 'description'), ('change_note_file', 'changeNote')]:
        name = settings.get(setting)
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f'{setting} 应为文件名或 null。')
            metadata[field] = (folder / name).read_text(encoding='utf-8-sig')
    for field in ('title', 'description', 'changeNote', 'minBranch', 'maxBranch'):
        if metadata.get(field) is not None and not isinstance(metadata[field], str):
            raise ValueError(f'{field} 应为文本或 null。')
    descriptors = {'nudity', 'frequent_violence', 'adult_only', 'gratuitous_nudity', 'general_mature'}
    for field in ('tags', 'contentDescriptors'):
        value = metadata.get(field)
        if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value)):
            raise ValueError(f'{field} 应为非空字符串组成的列表或 null。')
    if set(metadata.get('contentDescriptors') or []) - descriptors:
        raise ValueError('contentDescriptors 包含官方上传器不支持的值。')
    deps = metadata.get('dependencies')
    if not isinstance(deps, list) or any(type(x) is not int or not 0 < x < 2**64 for x in deps) or RITSULIB_ID not in deps:
        raise ValueError(f'dependencies 应为数字 ID 列表，并包含 RitsuLib：{RITSULIB_ID}。')
    if not read_item_id(folder) and not str(metadata.get('title') or '').strip():
        raise ValueError('首次上传请填写 title。')
    image = folder / 'image.png'
    data = image.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) >= 1_000_000:
        raise ValueError('image.png 必须是小于 1 MB 的 PNG 图片。')
    from PIL import Image
    with Image.open(image) as cover:
        cover.verify()
    executable = (folder / settings['uploader']).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f'未找到官方上传器：{executable}；安装方法见 docs/创意工坊上传工作流.md。')
    return metadata, executable


def stage_archive(folder: Path, archive_path: Path, manifest: dict, metadata: dict) -> Path:
    checksum = archive_path.with_suffix('.zip.sha256').read_text(encoding='ascii').split()[0]
    if sha256(archive_path) != checksum.upper():
        raise ValueError('发布 ZIP 的 SHA256 校验失败。')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        validate_archive_entries(set(names))
        if len(names) != 3 or archive.testzip() is not None:
            raise ValueError('发布 ZIP 有重复条目或损坏内容。')
        if json.loads(archive.read('RDmod.json')) != manifest:
            raise ValueError('发布包清单与当前 Mod 清单不一致，请重新构建。')
        payloads = {name: archive.read(name) for name in names}
    if any(not value for value in payloads.values()):
        raise ValueError('发布包包含空文件。')
    stage = folder / '.upload'
    content = stage / 'content'
    content.mkdir(parents=True, exist_ok=True)
    extra = {p.name for p in content.iterdir()} - set(payloads)
    if extra:
        raise ValueError(f'上传内容目录有额外文件，请移出后重试：{sorted(extra)}')
    for name, data in payloads.items():
        temporary = content / (name + '.tmp')
        temporary.write_bytes(data)
        os.replace(temporary, content / name)
    write_text(stage / 'workshop.json', json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    shutil.copyfile(folder / 'image.png', stage / 'image.png')
    item_id = read_item_id(folder)
    stage_id = stage / 'mod_id.txt'
    if item_id:
        save_item_id(folder, item_id)
        write_text(stage_id, item_id + '\n')
    elif stage_id.exists():
        raise ValueError('上传暂存目录已有 ID，但主 ID 丢失。请恢复 workshop/mod_id.txt，避免创建重复条目。')
    return stage


def upload(folder: Path, stage: Path, executable: Path) -> None:
    pending = folder / 'upload-pending.txt'
    item_id = read_item_id(folder)
    if pending.exists() and not item_id:
        raise ValueError('上次首次上传结果不确定。请查看上传日志和自己的工坊页面，恢复 mod_id.txt 后再试；确认未创建条目时才删除 upload-pending.txt。')
    write_text(pending, 'Upload started; preserve this marker and logs if interrupted.\n')
    logs = folder / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / (time.strftime('%Y%m%d-%H%M%S') + '-upload.log')
    print(f'上传日志：{log_path}', flush=True)
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(executable), 'upload', '-w', str(stage.resolve())],
                                   cwd=executable.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace')
        try:
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
                match = re.search(r'(?:with item ID |with id )(\d+)', line)
                if match:
                    save_item_id(folder, match.group(1))
            code = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    if code:
        raise subprocess.CalledProcessError(code, 'ModUploader upload')
    if not (stage / 'mod_id.txt').exists():
        raise RuntimeError('上传器未生成工坊 ID；请查看日志确认结果。')
    value = (stage / 'mod_id.txt').read_text(encoding='utf-8-sig').strip()
    if not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('上传器返回了无效 ID。')
    save_item_id(folder, value)
    pending.unlink()
    print(f'WORKSHOP_UPLOAD_OK https://steamcommunity.com/sharedfiles/filedetails/?id={value}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--upload', action='store_true', help='重新构建并上传；不额外询问确认。')
    mode.add_argument('--prepare', action='store_true', help='重新构建并准备内容，不连接 Steam。')
    mode.add_argument('--edit', action='store_true', help='打开可编辑工坊资料目录。')
    mode.add_argument('--github-only', action='store_true', help='构建并发布 GitHub 源码和安装包，不上传 Steam。')
    mode.add_argument('--login-github', action='store_true', help='登录 GitHub CLI。')
    mode.add_argument('--open-page', action='store_true', help='打开已保存 ID 的工坊页面。')
    args = parser.parse_args()
    if args.login_github:
        from publish_github import github_config
        repository, gh = github_config(WORKSHOP)
        print(f'请登录 {repository.split("/")[0]}', flush=True)
        return subprocess.run([str(gh), 'auth', 'login', '--hostname', 'github.com', '--git-protocol', 'https', '--web']).returncode
    if args.edit:
        os.startfile(str(WORKSHOP))
        return 0
    if args.open_page:
        item_id = read_item_id(WORKSHOP)
        if not item_id:
            raise ValueError('尚未上传；若已有工坊条目，请填写 workshop/mod_id.txt。')
        webbrowser.open(f'https://steamcommunity.com/sharedfiles/filedetails/?id={item_id}')
        return 0
    lock = WORKSHOP / '.workflow.lock'
    with lock.open('x'):
        pass
    try:
        metadata, executable = load_metadata(WORKSHOP)
        settings = read_json(WORKSHOP / 'settings.json')
        if settings.get('github'):
            from publish_github import github_config, media_files, public_files, render_description, publish
            repository, _ = github_config(WORKSHOP)
            media_files(WORKSHOP, metadata.get('description') or '')
            files = public_files(ROOT)
            write_text(WORKSHOP / 'github-preview.json', json.dumps({'repository': repository, 'files': list(files), 'bytes': sum(p.stat().st_size for p in files.values())}, ensure_ascii=False, indent=2))
        manifest = read_json(ROOT / 'Mod/RDmod.json')
        version = validate_release_version(manifest['version'])
        print(f"版本：{version}；标题：{metadata.get('title')}；可见性：{metadata.get('visibility', '保持线上设置')}；条目：{read_item_id(WORKSHOP) or '首次创建'}", flush=True)
        if not (args.upload or args.prepare or args.github_only):
            print('WORKSHOP_CHECK_OK；使用 --prepare 构建预览，--upload 构建上传。')
            return 0
        localization = ROOT / 'Mod/RDMod/localization'
        validate_localization_json(localization)
        validate_native_keyword_localization(ROOT / 'Mod/Cards', localization / 'zhs/cards.json')
        subprocess.run([sys.executable, str(ROOT / 'Scripts/package_local_release.py')], cwd=ROOT, check=True)
        archive = ROOT / 'dist' / f'RainbowDash-{version}.zip'
        # Validate the complete local package before creating any remote publication.
        stage = stage_archive(WORKSHOP, archive, manifest, metadata)
        if settings.get('github'):
            if args.upload or args.github_only:
                metadata = publish(ROOT, metadata, archive)
            elif metadata.get('description') is not None:
                metadata['description'] = render_description(metadata['description'], repository, 'main')
            stage = stage_archive(WORKSHOP, archive, manifest, metadata)
        print(f'WORKSHOP_PREPARED {stage}', flush=True)
        if args.upload:
            upload(WORKSHOP, stage, executable)
        return 0
    finally:
        lock.unlink(missing_ok=True)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'WORKSHOP_ERROR {exc}', file=sys.stderr)
        raise SystemExit(1)
