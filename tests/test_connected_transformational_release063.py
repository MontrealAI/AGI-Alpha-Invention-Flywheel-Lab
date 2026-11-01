import unittest
from scripts.release_connected014 import applicable_workflows


class TransformationalReleaseTests(unittest.TestCase):
    def test_current_kernel_and_paper_require_their_same_source_operation(self):
        for path in ('flexibility063/kernel.py', 'connected_enterprise/transformational063.py',
                     'campaign/transformational-063/TECHNICAL.json', 'docs/transformational063/paper.pdf'):
            with self.subTest(path=path):
                self.assertIn('transformational063.yml', applicable_workflows([path]))

    def test_changed_public_assets_require_website_validation(self):
        for path in ('docs/research/alpha.js', 'scripts/build_research_site.py', 'tests/test_alpha_site.cjs'):
            with self.subTest(path=path):
                self.assertIn('research-pages.yml', applicable_workflows([path]))

    def test_unrelated_historical_source_does_not_renew_the_experiment(self):
        self.assertNotIn('transformational063.yml', applicable_workflows(['docs/next009/PAPER.pdf']))


if __name__ == '__main__':
    unittest.main()
