#!/usr/bin/env python3
"""Keep two earlier published releases in the APT pool; full history stays in Releases."""
import json
import os
from pathlib import Path
import subprocess
import sys

repo, tag = os.environ['GITHUB_REPOSITORY'], sys.argv[1]
releases = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/releases?per_page=100'], text=True))
previous = [r for r in releases if not r['draft'] and not r['prerelease'] and r['tag_name'] != tag][:2]
destination = Path('site/pool/main/c/caddy')
destination.mkdir(parents=True, exist_ok=True)
for release in previous:
    subprocess.run(['gh', 'release', 'download', release['tag_name'], '--repo', repo,
                    '--pattern', '*.deb', '--dir', str(destination)], check=True)
