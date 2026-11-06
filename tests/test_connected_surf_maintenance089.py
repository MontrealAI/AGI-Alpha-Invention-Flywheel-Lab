"""Guard maintenance of the immutable SURF research release."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/surf-the-exponential.yml'


class SurfMaintenance089(unittest.TestCase):
    def test_first_step_of_both_jobs_records_platform_clock(self):
        raw = WORKFLOW.read_text()
        for name in ('build', 'release'):
            with self.subTest(job=name):
                steps = raw.split('  ' + name + ':\n', 1)[1].split('    steps:\n', 1)[1]
                first = steps.split('      - ', 2)[1]
                self.assertIn('AGI_JOB_START_EPOCH', first)
                self.assertIn('GITHUB_ENV', first)

    def test_constructive_companion_has_first_step_platform_clock(self):
        workflow = WORKFLOW.with_name('surf-constructive-challenge.yml')
        raw = workflow.read_text()
        steps = raw.split('  qualify:\n', 1)[1].split('    steps:\n', 1)[1]
        first = steps.split('      - ', 2)[1]
        self.assertIn('AGI_JOB_START_EPOCH', first)
        self.assertIn('GITHUB_ENV', first)
        self.assertNotIn('actions/checkout', first)

    def test_maintenance_commit_cannot_change_immutable_edition(self):
        text = WORKFLOW.read_text()
        self.assertIn('tag=surf-the-exponential-v1.2.0', text)
        self.assertIn('SURF_EXISTING_IMMUTABLE_EDITION', text)
        self.assertIn('tag_commit="$(gh api "repos/$GITHUB_REPOSITORY/commits/$tag" --jq .sha)"', text)
        self.assertIn('SURF_EXISTING_TAG_DRAFT_MISMATCH', text)
        self.assertIn('cmp "$assets/$f" "$RUNNER_TEMP/surf-downloaded/$f"', text)
        self.assertIn('sha256sum --check SHA256SUMS', text)


if __name__ == '__main__':
    unittest.main()
