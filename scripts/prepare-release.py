#!/usr/bin/env python3
import json
import os
import re
import subprocess


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


config = json.load(open('build-config.json'))
release = api('repos/caddyserver/caddy/releases/latest')
version = release['tag_name']
if not re.fullmatch(r'v\d+\.\d+\.\d+', version) or release['prerelease'] or release['draft']:
    raise SystemExit('Expected an upstream stable vX.Y.Z release')
revision = config['package_revision']
if type(revision) is not int or revision < 1:
    raise SystemExit('package_revision must be a positive integer')
tag = f'{version}-custom.{revision}'
releases = api(f'repos/{os.environ["GITHUB_REPOSITORY"]}/releases?per_page=100')
exists = any(r['tag_name'] == tag and not r['draft'] for r in releases)
with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
    out.write(f'version={version}\ntag={tag}\npackage_version={version[1:]}-1+custom.{revision}\n')
    out.write(f'build={str(not exists).lower()}\n')
print(f'{tag}: {"already published" if exists else "build required"}')
