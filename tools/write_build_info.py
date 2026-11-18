"""Generate image build information instead of shipping stale upstream metadata."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--revision', required=True)
parser.add_argument('--version', required=True)
args = parser.parse_args()
version = Path('VERSION').read_text().strip()
if version != args.version:
    raise SystemExit('Docker APP_VERSION must match VERSION')
now = datetime.now(timezone.utc)
Path('BUILD_INFO').write_text(json.dumps({
    'version': version, 'full_version': version, 'git_commit': args.revision,
    'build_type': 'container', 'build_timestamp': now.strftime('%Y%m%d-%H%M%S'),
    'build_date': now.isoformat(), 'build_unix': int(now.timestamp()),
}, indent=2) + '\n')
