#!/usr/bin/env python3
"""Resolve one immutable input snapshot shared by both architecture builds."""
import json
import os
from pathlib import Path

from release_state import resolve_plan, stable_release


def main():
    config = json.loads(Path('build-config.json').read_text())
    plan = resolve_plan(os.environ['GITHUB_REPOSITORY'], config)
    if plan['build']:
        # Resolve once at build preparation, not independently on each runner.
        plan['xcaddy'] = stable_release('caddyserver/xcaddy')
        Path('build-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
        for key, value in {'version': plan['upstream_version'], 'tag': plan['tag'],
                           'package_version': plan['package_version'], 'build': str(plan['build']).lower()}.items():
            out.write(f'{key}={value}\n')
    print(f'{plan["tag"]}: {"build required" if plan["build"] else "all upstream inputs already published"}')


if __name__ == '__main__':
    main()
