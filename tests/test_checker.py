import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'scripts/check-update.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CheckUpdateTests(unittest.TestCase):
    def invoke(self, build=True, runs=None, check_only=False):
        replies = [json.dumps({'packaging_revision': 1}), json.dumps({'workflow_runs': runs or []})]
        with patch.object(checker, 'gh', side_effect=replies), patch.object(checker, 'resolve_plan',
                return_value={'tag': 'v2.11.9-custom.3', 'build': build}), patch.object(checker.subprocess, 'run') as run:
            checker.check('owner/repo', check_only)
            return run.call_args_list

    def test_published_inputs_do_not_dispatch(self):
        self.assertEqual(self.invoke(build=False), [])

    def test_changed_inputs_dispatch(self):
        calls = self.invoke()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0], ['gh', 'workflow', 'run', 'release.yml', '--repo', 'owner/repo', '--ref', 'main'])

    def test_failed_workflow_is_retried(self):
        self.assertEqual(len(self.invoke(runs=[{'status': 'completed', 'conclusion': 'failure'}])), 1)

    def test_active_workflow_is_not_duplicated(self):
        self.assertEqual(self.invoke(runs=[{'status': 'in_progress'}]), [])

    def test_check_only_never_dispatches(self):
        self.assertEqual(self.invoke(check_only=True), [])

    def test_network_error_is_not_an_update(self):
        with patch.object(checker, 'gh', side_effect=subprocess.CalledProcessError(1, ['gh'])), patch.object(checker.subprocess, 'run') as run:
            with self.assertRaises(subprocess.CalledProcessError):
                checker.check('owner/repo')
            run.assert_not_called()
