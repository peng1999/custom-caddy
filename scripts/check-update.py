#!/usr/bin/env python3
"""Check upstream and dispatch a build. No repository writes or local version cache."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile

from release_state import gh, resolve_plan


def check(repo, check_only=False):
    # Config is read from GitHub, while shared planning compares actual release manifests.
    config = json.loads(gh('api', f'repos/{repo}/contents/build-config.json',
                          '-H', 'Accept: application/vnd.github.raw+json'))
    plan = resolve_plan(repo, config)
    tag = plan['tag']
    if not plan['build']:
        print(f'{tag}: Caddy and both plugins are already published.')
        return
    print(f'{tag} needs publication.', flush=True)
    if check_only:
        return
    runs = json.loads(gh('api', f'repos/{repo}/actions/workflows/release.yml/runs?per_page=100'))
    if any(r['status'] != 'completed' for r in runs['workflow_runs']):
        print('A release workflow is already queued or running; skipping.')
        return
    subprocess.run(['gh', 'workflow', 'run', 'release.yml', '--repo', repo, '--ref', 'main'], check=True)
    print('Build dispatched. Failed builds will be retried on the next check.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='peng1999/custom-caddy')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    # Prevent simultaneous local timer/manual invocations; GitHub also serializes publication.
    lockdir = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir()))
    with (lockdir / f'custom-caddy-check-{os.getuid()}.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        check(args.repo, args.check_only)


if __name__ == '__main__':
    main()
