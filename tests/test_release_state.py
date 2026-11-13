import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import release_state as state

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'scripts/prepare-release.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def release(n, version='v2.11.9', draft=False, assets=True):
    return {'tag_name': f'{version}-custom.{n}', 'draft': draft, 'prerelease': False,
            'assets': [{'name': 'manifest.json'}] if assets else []}


class ReleasePlanningTests(unittest.TestCase):
    def setUp(self):
        self.inputs = {'upstream_version': 'v2.11.9', 'cloudflare': 'a' * 40,
                       'dynamicdns': 'b' * 40, 'packaging_revision': 1}

    def plan(self, inputs=None, recorded=None, releases=None):
        with patch.object(state, 'manifest', return_value=recorded if recorded is not None else self.inputs):
            return state.plan_release('owner/repo', inputs or self.inputs,
                                      releases if releases is not None else [release(2)])

    def test_unchanged_inputs_skip_even_with_new_xcaddy(self):
        plan = self.plan(recorded=dict(self.inputs, xcaddy='v0.1.0'))
        self.assertFalse(plan['build'])
        self.assertEqual(plan['tag'], 'v2.11.9-custom.2')

    def test_each_plugin_update_increments_revision(self):
        for plugin in state.PLUGINS:
            with self.subTest(plugin=plugin):
                plan = self.plan(inputs=dict(self.inputs, **{plugin: 'c' * 40}))
                self.assertTrue(plan['build'])
                self.assertEqual(plan['package_version'], '2.11.9-1+custom.3')

    def test_simultaneous_plugin_updates_make_one_revision(self):
        self.assertEqual(self.plan(inputs=dict(self.inputs, cloudflare='c' * 40, dynamicdns='d' * 40))['package_revision'], 3)

    def test_new_caddy_starts_revision_one_and_uses_newest_plugins(self):
        inputs = dict(self.inputs, upstream_version='v2.12.0', cloudflare='c' * 40)
        plan = self.plan(inputs=inputs)
        self.assertEqual(plan['tag'], 'v2.12.0-custom.1')
        self.assertEqual(plan['cloudflare'], 'c' * 40)

    def test_numeric_revision_order(self):
        plan = self.plan(inputs=dict(self.inputs, dynamicdns='c' * 40), releases=[release(9), release(10), release(2)])
        self.assertEqual(plan['package_revision'], 11)

    def test_packaging_generation_forces_manual_rebuild(self):
        self.assertEqual(self.plan(inputs=dict(self.inputs, packaging_revision=2))['package_revision'], 3)

    def test_legacy_manifest_migrates_once(self):
        legacy = dict(self.inputs)
        del legacy['packaging_revision']
        self.assertEqual(self.plan(recorded=legacy)['package_revision'], 3)

    def test_matching_draft_is_resumed(self):
        # A first publication failed after artifacts were staged.
        plan = self.plan(releases=[release(1, draft=True)])
        self.assertTrue(plan['build'])
        self.assertEqual(plan['package_revision'], 1)

    def test_draft_with_old_inputs_is_not_reused(self):
        plan = self.plan(inputs=dict(self.inputs, cloudflare='c' * 40), releases=[release(3, draft=True), release(2)])
        self.assertEqual(plan['package_revision'], 4)

    def test_empty_draft_is_reserved_without_claiming_success(self):
        plan = self.plan(releases=[release(1, draft=True, assets=False)])
        self.assertTrue(plan['build'])
        self.assertEqual(plan['package_revision'], 2)

    def test_manifest_fetch_error_does_not_allocate_new_release(self):
        with patch.object(state, 'manifest', side_effect=subprocess.CalledProcessError(1, ['gh'])):
            with self.assertRaises(subprocess.CalledProcessError):
                state.plan_release('owner/repo', self.inputs, [release(2)])

    def test_pagination_is_not_limited_to_first_hundred_releases(self):
        with patch.object(state, 'gh', return_value=json.dumps([[release(2)], [release(1)]])) as gh:
            self.assertEqual(len(state.all_releases('owner/repo')), 2)
            self.assertIn('--paginate', gh.call_args.args)

    def test_resolves_default_branch_sha_and_validates_stable_caddy(self):
        responses = [{'tag_name': 'v2.12.0', 'draft': False, 'prerelease': False},
                     {'sha': 'a' * 40}, {'sha': 'b' * 40}]
        with patch.object(state, 'api', side_effect=responses) as api:
            inputs = state.upstream_inputs({'packaging_revision': 1})
            self.assertEqual(inputs['cloudflare'], 'a' * 40)
            self.assertEqual(api.call_args_list[1].args[0], 'repos/caddy-dns/cloudflare/commits/HEAD')

    def test_prerelease_caddy_is_rejected(self):
        with patch.object(state, 'api', return_value={'tag_name': 'v2.12.0-rc1', 'draft': False, 'prerelease': True}):
            with self.assertRaises(ValueError):
                state.upstream_inputs({'packaging_revision': 1})


class BuildSnapshotTests(unittest.TestCase):
    def test_latest_xcaddy_is_resolved_once_and_frozen(self):
        for build in (True, False):
            with self.subTest(build=build), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'build-config.json').write_text('{"packaging_revision": 1}')
                plan = {'build': build, 'upstream_version': 'v2.11.9', 'tag': 'v2.11.9-custom.3',
                        'package_version': '2.11.9-1+custom.3', 'cloudflare': 'a' * 40, 'dynamicdns': 'b' * 40}
                previous = os.getcwd()
                try:
                    os.chdir(root)
                    with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_OUTPUT': str(root / 'outputs')}), \
                            patch.object(prepare, 'resolve_plan', return_value=plan), \
                            patch.object(prepare, 'stable_release', return_value='v9.0.0') as latest:
                        prepare.main()
                        if build:
                            latest.assert_called_once_with('caddyserver/xcaddy')
                            self.assertEqual(json.loads((root / 'build-plan.json').read_text())['xcaddy'], 'v9.0.0')
                        else:
                            latest.assert_not_called()
                            self.assertFalse((root / 'build-plan.json').exists())
                finally:
                    os.chdir(previous)
