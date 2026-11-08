#!/usr/bin/env python3
"""Regression tests for installer source/output separation without installation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import setup_incumbent


class SetupBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ltb-setup-boundary-")
        self.base = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)

    def check_boundary(self, construction, boundary):
        construction.mkdir(parents=True, exist_ok=True)
        with patch.object(setup_incumbent, "ROOT", construction):
            self.assertEqual(setup_incumbent.source_boundary(), boundary)
            with self.assertRaisesRegex(ValueError, "outside the repository/source edition"):
                setup_incumbent.outside_edition(boundary / "runtime")
            with self.assertRaisesRegex(ValueError, "outside the repository/source edition"):
                setup_incumbent.outside_edition(boundary)
            sibling = boundary.parent / "external-runtime"
            self.assertEqual(setup_incumbent.outside_edition(sibling), sibling)

    def test_checkout_protects_the_entire_repository(self):
        repo = self.base / "checkout"
        (repo / ".git").mkdir(parents=True)
        self.check_boundary(repo / "docs/learning-to-build-v1.1.0/construction", repo)

    def test_worktree_git_file_protects_the_entire_repository(self):
        repo = self.base / "worktree"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: /unread/external/gitdir\n")
        self.check_boundary(repo / "docs/learning-to-build-v1.1.0/construction", repo)

    def test_extracted_source_protects_the_edition(self):
        edition = self.base / "extracted"
        self.check_boundary(edition / "construction", edition)

    def test_ambient_git_repository_does_not_block_sibling_workspace(self):
        (self.base / ".git").mkdir()
        edition = self.base / "scratch/extracted"
        self.check_boundary(edition / "construction", edition)

    def test_same_named_edition_inside_ambient_git_is_still_an_extract(self):
        (self.base / ".git").mkdir()
        edition = self.base / "scratch/learning-to-build-v1.1.0"
        self.check_boundary(edition / "construction", edition)

    def test_symlink_into_protected_source_is_rejected(self):
        edition = self.base / "extracted"
        construction = edition / "construction"
        construction.mkdir(parents=True)
        alias = self.base / "outside-looking-link"
        alias.symlink_to(edition, target_is_directory=True)
        with patch.object(setup_incumbent, "ROOT", construction):
            with self.assertRaisesRegex(ValueError, "outside the repository/source edition"):
                setup_incumbent.outside_edition(alias / "runtime")

    def test_relative_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            setup_incumbent.outside_edition(Path("relative-runtime"))


if __name__ == "__main__":
    unittest.main()
