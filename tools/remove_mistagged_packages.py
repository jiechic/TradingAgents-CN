"""One-time removal of the incorrectly published stable version; never deletes a package."""
import json
import os
import subprocess

owner = os.environ['OWNER']
execute = os.environ.get('EXECUTE') == 'true'
wrong = {'v3.0.0', 'v3.0.0-amd64', 'v3.0.0-arm64'}
replacement = 'v3.0.0-beta.4'


def api(path, method='GET'):
    result = subprocess.run(['gh', 'api', path, '--method', method], capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


# Check both packages completely before making any deletion.
planned = []
for package in ('tradingagents-v3-backend', 'tradingagents-v3-frontend'):
    endpoint = f'users/{owner}/packages/container/{package}/versions'
    versions = []
    for page in range(1, 101):
        batch = api(f'{endpoint}?per_page=100&page={page}')
        versions.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError('Unexpected package version count; refusing partial cleanup')
    if not any(replacement in v['metadata']['container']['tags'] for v in versions):
        raise RuntimeError(f'{package}: replacement {replacement} must exist before removal')
    for version in versions:
        tags = set(version['metadata']['container']['tags'])
        if tags & wrong:
            if tags - wrong:
                raise RuntimeError(f'{package}: shared digest has other tags {sorted(tags)}; refusing deletion')
            planned.append((endpoint, version['id'], package, sorted(tags)))
for endpoint, version_id, package, tags in planned:
    print('DELETE' if execute else 'WOULD DELETE', package, version_id, tags, flush=True)
    if execute:
        api(f'{endpoint}/{version_id}', 'DELETE')
if execute:
    for package in ('tradingagents-v3-backend', 'tradingagents-v3-frontend'):
        endpoint = f'users/{owner}/packages/container/{package}/versions'
        for page in range(1, 101):
            batch = api(f'{endpoint}?per_page=100&page={page}')
            assert all(not (set(v['metadata']['container']['tags']) & wrong) for v in batch)
            if len(batch) < 100:
                break
    print('Mistaken stable versions removed; beta.4 and all other versions retained.')
