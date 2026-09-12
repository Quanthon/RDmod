#!/usr/bin/env python3
"""Publish an explicit RDmod source snapshot, release ZIP and description media."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

LOCAL_IMAGE = re.compile(r'\[img\]\s*(media/[^\[\]\r\n]+)\s*\[/img\]', re.IGNORECASE)
SOURCE_TYPES = {'.cs', '.csproj', '.sln', '.gd', '.tscn', '.tres', '.gdshader', '.json',
                '.md', '.ai', '.png', '.webp', '.jpg', '.jpeg', '.svg', '.ogg', '.mp3', '.wav', '.import', '.uid', '.cfg', '.godot'}


def github_config(folder: Path) -> tuple[str, Path]:
    settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8-sig'))
    config = settings.get('github')
    if not isinstance(config, dict):
        raise ValueError('请配置 settings.json 的 github.repository 和 github.cli。')
    repo = config.get('repository', '')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repo) or repo.split('/')[1] in {'.', '..'}:
        raise ValueError('github.repository 应为 owner/repository。')
    executable = (folder / config['cli']).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f'未找到 GitHub CLI：{executable}')
    return repo, executable


def media_files(folder: Path, text: str) -> dict[str, Path]:
    result = {}
    base = (folder / 'media').resolve()
    from PIL import Image
    for match in LOCAL_IMAGE.finditer(text):
        name = match.group(1).strip()
        if '\\' in name or any(x in {'.', '..', ''} for x in name.split('/')):
            raise ValueError(f'无效描述图片路径：{name}')
        path = (folder / name).resolve()
        if not path.is_relative_to(base) or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
            raise ValueError(f'描述图片必须位于 workshop/media：{name}')
        if path.stat().st_size >= 20 * 1024 * 1024:
            raise ValueError(f'描述图片请控制在20MB以内：{name}')
        with Image.open(path) as image:
            image.verify()
        result[name] = path
    return result


def render_description(text: str, repository: str, revision: str) -> str:
    def replace(match):
        name = match.group(1).strip()
        url = f'https://raw.githubusercontent.com/{repository}/{quote(revision, safe="")}/workshop/{quote(name, safe="/")}'
        return f'[img]{url}[/img]'
    return LOCAL_IMAGE.sub(replace, text)


def public_files(root: Path) -> dict[str, Path]:
    """Explicit allowlist: no repository history, design workbook, logs or binaries."""
    files = {}
    def add(path):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'公开文件不能指向项目外：{path}')
        files[path.relative_to(root).as_posix()] = path
    for path in (root / 'Mod').rglob('*'):
        if not path.is_file() or any(part in {'.godot', '.vscode', 'bin', 'obj', '.git'} for part in path.relative_to(root / 'Mod').parts[:-1]):
            continue
        if path.suffix.lower() in SOURCE_TYPES:
            add(path)
    for relative in ('.gitignore', 'README.md', 'LICENSE', 'ASSET_NOTICE.md',
                     'Scripts/package_local_release.py', 'Scripts/publish_github.py',
                     'Scripts/upload_workshop.py', 'Scripts/release_validation.py',
                     'docs/创意工坊上传工作流.md',
                     'workshop/settings.json', 'workshop/workshop.json', 'workshop/description.txt',
                     'workshop/changelog.txt', 'workshop/image.png', 'workshop/使用说明.txt'):
        path = root / relative
        if path.is_file():
            add(path)
    for path in root.glob('*.bat'):
        # Only ship publication entry points, not unrelated local tooling.
        if path.stem in {'打包发布', '上传创意工坊', '准备工坊上传', '编辑工坊资料', '打开工坊页面', '发布GitHub', '登录GitHub'}:
            add(path)
    folder = root / 'workshop'
    settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8-sig'))
    source = settings.get('description_file')
    text = (folder / source).read_text(encoding='utf-8-sig') if source else ''
    for name, path in media_files(folder, text).items():
        files['workshop/' + name] = path
    for name in ('Mod/RDmod.csproj', 'Mod/RDmod.json', 'README.md', 'LICENSE'):
        if name not in files:
            raise ValueError(f'公开源码缺少必要文件：{name}')
    return dict(sorted(files.items()))


def run(command: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, check=check, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def verify_raw(url: str, source: Path) -> None:
    expected = hashlib.sha256(source.read_bytes()).digest()
    error = None
    for attempt in range(5):
        try:
            # Deliberately anonymous: description images must work for every visitor.
            with urllib.request.urlopen(url, timeout=20) as response:
                actual = hashlib.sha256(response.read(source.stat().st_size + 1)).digest()
            if actual != expected:
                raise ValueError('图片内容校验失败')
            return
        except (OSError, ValueError) as exc:
            error = exc
            if attempt < 4:
                time.sleep(2)
    raise RuntimeError(f'GitHub 图片尚不能匿名读取：{url}；{error}')


def publish(root: Path, metadata: dict, archive: Path, *, approved_removals: set[str] | None = None) -> dict:
    folder = root / 'workshop'
    repository, gh = github_config(folder)
    files = public_files(root)
    def cli(*args, check=True):
        return run([str(gh), *args], check=check)
    auth = cli('api', 'user', '--jq', '.login', check=False)
    if auth.returncode or auth.stdout.strip().lower() != repository.split('/')[0].lower():
        raise RuntimeError(f'请先运行 登录GitHub.bat，登录 {repository.split("/")[0]} 后重试。')
    view = cli('api', 'repos/' + repository, check=False)
    if view.returncode:
        if '404' not in view.stderr:
            raise RuntimeError('无法读取 GitHub 仓库：' + view.stderr)
        created = cli('api', 'user/repos', '-X', 'POST', '-f', 'name=' + repository.split('/')[1],
                      '-F', 'private=false', '-F', 'auto_init=true', '-f', 'description=Rainbow Dash character mod for Slay the Spire 2')
        remote = json.loads(created.stdout)
    else:
        remote = json.loads(view.stdout)
    if remote.get('private') or remote.get('archived'):
        raise ValueError('目标仓库必须为公开且未归档；此流程不会自动公开已有私有仓库。')
    branch = remote['default_branch']
    checkout = root / '.tools' / 'github-publish' / repository.replace('/', '--')
    checkout.parent.mkdir(parents=True, exist_ok=True)
    url = 'https://github.com/' + repository + '.git'
    credentials = ['-c', 'credential.helper=', '-c', f'credential.helper=!"{gh.as_posix()}" auth git-credential']
    def git(*args):
        return run(['git', '--literal-pathspecs', *credentials, *args], cwd=checkout)
    if not checkout.exists():
        run(['git', *credentials, 'clone', '--single-branch', '--branch', branch, url, str(checkout)])
    if git('remote', 'get-url', 'origin').stdout.strip() != url:
        raise ValueError('公开快照目录的 Git 远程不匹配，请检查 .tools/github-publish。')
    git('fetch', 'origin', branch)
    # Keep failed local commits for a retry; refuse divergent history instead of forcing.
    git('merge', '--ff-only', 'origin/' + branch)
    index_file = checkout / '.rdmod-public-files.json'
    removed = set()
    if index_file.exists():
        previous = set(json.loads(index_file.read_text(encoding='utf-8')))
        removed = previous - set(files)
        if removed - (approved_removals or set()):
            raise ValueError(f'先确认已移除源码的远程处理，再更新公开清单：{sorted(removed)}')
        for name in removed:
            target = checkout / name
            if not target.resolve().is_relative_to(checkout.resolve()) or '.git' in target.relative_to(checkout).parts:
                raise ValueError('删除路径越界：' + name)
    staged = set(filter(None, git('diff', '--cached', '--name-only', '-z').stdout.split('\0')))
    if staged - set(files) - (approved_removals or set()) - {'.rdmod-public-files.json'}:
        raise ValueError('公开快照目录包含未列入发布清单的暂存改动。')
    if removed:
        git('rm', '--ignore-unmatch', '--', *sorted(removed))
    for name, source in files.items():
        target = checkout / name
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError('公开快照路径越界：' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Only add the reviewed file set; never git add the original project or history.
    for offset in range(0, len(files), 100):
        git('add', '--', *list(files)[offset:offset+100])
    index_file.write_text(json.dumps(list(files), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    git('add', '--', '.rdmod-public-files.json')
    if git('diff', '--cached', '--name-only').stdout.strip():
        version = json.loads((root / 'Mod/RDmod.json').read_text(encoding='utf-8-sig'))['version']
        git('-c', 'user.name=Quanthon', '-c', 'user.email=53946379+Quanthon@users.noreply.github.com',
            'commit', '-m', f'Publish Rainbow Dash {version} source and assets')
    git('push', 'origin', 'HEAD:' + branch)
    revision = git('rev-parse', 'HEAD').stdout.strip()
    result = dict(metadata)
    text = result.get('description') or ''
    for name, source in media_files(folder, text).items():
        raw = f'https://raw.githubusercontent.com/{repository}/{revision}/workshop/{quote(name, safe="/")}'
        verify_raw(raw, source)
    result['description'] = render_description(text, repository, revision) if metadata.get('description') is not None else None
    version = json.loads((root / 'Mod/RDmod.json').read_text(encoding='utf-8-sig'))['version']
    tag = 'v' + version
    existing = cli('api', f'repos/{repository}/releases/tags/{quote(tag, safe="")}', check=False)
    if existing.returncode:
        if '404' not in existing.stderr:
            raise RuntimeError('无法读取 GitHub Release：' + existing.stderr)
        cli('release', 'create', tag, str(archive), str(archive.with_suffix('.zip.sha256')),
            '--repo', repository, '--target', revision, '--title', 'Rainbow Dash ' + version,
            '--notes-file', str(folder / 'changelog.txt'))
    else:
        cli('release', 'upload', tag, str(archive), str(archive.with_suffix('.zip.sha256')), '--repo', repository, '--clobber')
    release_data = json.loads(cli('api', f'repos/{repository}/releases/tags/{quote(tag, safe="")}').stdout)
    assets = {asset['name']: asset for asset in release_data['assets']}
    for path in (archive, archive.with_suffix('.zip.sha256')):
        asset = assets.get(path.name)
        if not asset or asset['size'] != path.stat().st_size:
            raise RuntimeError(f'GitHub Release 文件缺失或大小不符：{path.name}')
        digest = asset.get('digest')
        if digest and digest != 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest():
            raise RuntimeError(f'GitHub Release 文件哈希不符：{path.name}')
    report = {'repository': repository, 'commit': revision, 'release': f'https://github.com/{repository}/releases/tag/{tag}',
              'files': len(files), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    (folder / 'github-published.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('GITHUB_PUBLISHED ' + report['release'], flush=True)
    return result
