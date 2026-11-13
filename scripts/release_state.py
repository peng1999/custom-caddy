"""Resolve upstream inputs and plan monotonically versioned, immutable releases."""
import json
import re
import subprocess

PLUGINS = {'cloudflare': 'caddy-dns/cloudflare', 'dynamicdns': 'mholt/caddy-dynamicdns'}
IDENTITY = ('upstream_version', 'cloudflare', 'dynamicdns', 'packaging_revision')


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def api(path):
    return json.loads(gh('api', path))


def stable_release(repo):
    release = api(f'repos/{repo}/releases/latest')
    tag = release['tag_name']
    if release['draft'] or release['prerelease'] or not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError(f'{repo}: expected a stable vX.Y.Z release')
    return tag


def upstream_inputs(config):
    generation = config['packaging_revision']
    if type(generation) is not int or generation < 1:
        raise ValueError('packaging_revision must be a positive integer')
    inputs = {'upstream_version': stable_release('caddyserver/caddy'), 'packaging_revision': generation}
    for name, repo in PLUGINS.items():
        commit = api(f'repos/{repo}/commits/HEAD')['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError(f'{repo}: expected a full commit SHA')
        inputs[name] = commit
    return inputs


def all_releases(repo):
    pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
    return [release for page in pages for release in page]


def manifest(repo, release):
    # A missing/corrupt published manifest is an error, never evidence of an update.
    return json.loads(gh('release', 'download', release['tag_name'], '--repo', repo,
                         '--pattern', 'manifest.json', '--output', '-'))


def matches(inputs, recorded):
    return all(recorded.get(key) == inputs[key] for key in IDENTITY)


def plan_release(repo, inputs, releases):
    pattern = re.compile(re.escape(inputs['upstream_version']) + r'-custom\.([1-9]\d*)')
    candidates = []
    for release in releases:
        match = pattern.fullmatch(release['tag_name'])
        if match and not release['prerelease']:
            candidates.append((int(match[1]), release))
    candidates.sort(key=lambda item: item[0], reverse=True)
    published = next(((n, r) for n, r in candidates if not r['draft']), None)
    build = True
    if published and matches(inputs, manifest(repo, published[1])):
        revision, build = published[0], False
    else:
        # Retry an interrupted publication only when its exact inputs still match.
        draft = next((n for n, r in candidates
                      if r['draft'] and (not published or n > published[0])
                      and any(a['name'] == 'manifest.json' for a in r['assets'])
                      and matches(inputs, manifest(repo, r))), None)
        revision = draft if draft is not None else max((n for n, _ in candidates), default=0) + 1
    return dict(inputs, build=build, package_revision=revision,
                tag=f'{inputs["upstream_version"]}-custom.{revision}',
                package_version=f'{inputs["upstream_version"][1:]}-1+custom.{revision}')


def resolve_plan(repo, config):
    return plan_release(repo, upstream_inputs(config), all_releases(repo))
