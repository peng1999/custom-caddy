import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'scripts/check-update.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CheckUpdateTests(unittest.TestCase):
    def responses(self, releases=None, runs=None):
        return [json.dumps({'tag_name': 'v2.11.9'}),
                json.dumps({'package_revision': 1}),
                json.dumps(releases or []),
                json.dumps({'workflow_runs': runs or []})]

    def test_published_release_does_not_dispatch(self):
        releases = [{'tag_name': 'v2.11.9-custom.1', 'draft': False}]
        with patch.object(checker, 'gh', side_effect=self.responses(releases)), patch.object(checker.subprocess, 'run') as run:
            checker.check('owner/repo')
            run.assert_not_called()

    def test_failed_publication_draft_is_retried(self):
        releases = [{'tag_name': 'v2.11.9-custom.1', 'draft': True}]
        with patch.object(checker, 'gh', side_effect=self.responses(releases, [{'status': 'completed', 'conclusion': 'failure'}])), patch.object(checker.subprocess, 'run') as run:
            checker.check('owner/repo')
            run.assert_called_once_with(['gh', 'workflow', 'run', 'release.yml', '--repo', 'owner/repo', '--ref', 'main'], check=True)

    def test_active_build_does_not_duplicate(self):
        with patch.object(checker, 'gh', side_effect=self.responses(runs=[{'status': 'in_progress'}])), patch.object(checker.subprocess, 'run') as run:
            checker.check('owner/repo')
            run.assert_not_called()

    def test_check_only_never_dispatches(self):
        with patch.object(checker, 'gh', side_effect=self.responses()), patch.object(checker.subprocess, 'run') as run:
            checker.check('owner/repo', check_only=True)
            run.assert_not_called()

    def test_network_failure_is_not_treated_as_missing_release(self):
        with patch.object(checker, 'gh', side_effect=subprocess.CalledProcessError(1, ['gh'])), patch.object(checker.subprocess, 'run') as run:
            with self.assertRaises(subprocess.CalledProcessError):
                checker.check('owner/repo')
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
