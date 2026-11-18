#!/usr/bin/env python3
"""Validate release metadata, or update it with --set 3.0.0-beta.5."""
import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = r'3\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?'


def check_version(value):
    if not re.fullmatch(PATTERN, value):
        raise ValueError(f'Unsupported release version: {value!r}')
    return value


def update(version):
    check_version(version)
    (ROOT / 'VERSION').write_text(version + '\n')
    path = ROOT / 'pyproject.toml'
    path.write_text(re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', path.read_text(), count=1))
    for name in ('frontend/package.json', 'frontend/package-lock.json'):
        path = ROOT / name
        data = json.loads(path.read_text())
        data['version'] = version
        if 'packages' in data:
            data['packages']['']['version'] = version
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    path = ROOT / 'tradingagents/__init__.py'
    path.write_text(re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"', path.read_text()))
    path = ROOT / 'BUILD_INFO'
    data = {'version': version, 'full_version': version, 'build_type': 'source',
            'git_commit': None, 'build_timestamp': None, 'build_date': None, 'build_unix': None}
    path.write_text(json.dumps(data, indent=2) + '\n')
    for name in ('deploy/portainer-v3.yml', 'deploy/README-v3.md', 'README.md'):
        path = ROOT / name
        path.write_text(re.sub(r'v' + PATTERN, 'v' + version, path.read_text()))


def validate():
    version = check_version((ROOT / 'VERSION').read_text().strip())
    found = {'VERSION': version}
    found['pyproject.toml'] = re.search(r'(?m)^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text())[1]
    for name in ('frontend/package.json', 'frontend/package-lock.json'):
        data = json.loads((ROOT / name).read_text())
        found[name] = data['version']
        if 'packages' in data:
            found[name + ' root package'] = data['packages']['']['version']
    tree = ast.parse((ROOT / 'tradingagents/__init__.py').read_text())
    found['tradingagents.__version__'] = next(ast.literal_eval(n.value) for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    info = json.loads((ROOT / 'BUILD_INFO').read_text(encoding='utf-8-sig'))
    found['BUILD_INFO.version'] = info['version']
    found['BUILD_INFO.full_version'] = info['full_version']
    compose = (ROOT / 'deploy/portainer-v3.yml').read_text()
    for component in ('backend', 'frontend'):
        found['deploy.' + component] = re.search(r'tradingagents-v3-' + component + r':v([^\s]+)', compose)[1]
    errors = [f'{name}: {value!r}, expected {version!r}' for name, value in found.items() if value != version]
    if errors:
        raise ValueError('\n'.join(errors))
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--set', dest='version')
    args = parser.parse_args()
    if args.version:
        update(args.version)
    print(validate())
