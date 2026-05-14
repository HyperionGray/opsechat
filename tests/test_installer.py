#!/usr/bin/env python3
"""
Tests for current installation entrypoints and setup documentation.

The legacy root-level install.sh flow has been removed. These tests verify the
supported replacement paths: top-level docs plus the developer bootstrap
helper.
"""

import os
import subprocess
import unittest


class TestInstallEntryPoints(unittest.TestCase):
    """Validate the supported setup docs and helper scripts."""

    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.bootstrap_script = os.path.join(
            self.repo_root, 'scripts', 'bootstrap-dev-environment.sh'
        )
        self.uninstall_script = os.path.join(self.repo_root, 'uninstall.sh')
        self.install_doc = os.path.join(self.repo_root, 'docs', 'setup', 'INSTALL.md')
        self.quickstart_doc = os.path.join(self.repo_root, 'QUICKSTART.md')
        self.readme = os.path.join(self.repo_root, 'README.md')

    def test_install_documentation_exists(self):
        self.assertTrue(os.path.exists(self.install_doc))
        self.assertTrue(os.path.exists(self.quickstart_doc))
        self.assertFalse(os.path.exists(os.path.join(self.repo_root, 'INSTALL.md')))

    def test_bootstrap_script_exists(self):
        self.assertTrue(os.path.exists(self.bootstrap_script))
        self.assertTrue(os.access(self.bootstrap_script, os.X_OK))

    def test_uninstall_script_exists(self):
        self.assertTrue(os.path.exists(self.uninstall_script))
        self.assertTrue(os.access(self.uninstall_script, os.X_OK))

    def test_bootstrap_script_syntax(self):
        result = subprocess.run(
            ['bash', '-n', self.bootstrap_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_uninstall_script_syntax(self):
        result = subprocess.run(
            ['bash', '-n', self.uninstall_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bootstrap_script_has_strict_mode(self):
        with open(self.bootstrap_script, 'r') as f:
            content = f.read()

        self.assertIn('#!/usr/bin/env bash', content)
        self.assertIn('set -euo pipefail', content)
        self.assertIn('python3 -m venv', content)
        self.assertIn('requirements.txt', content)
        self.assertIn('requirements-dev.txt', content)

    def test_install_doc_describes_current_entrypoints(self):
        with open(self.install_doc, 'r') as f:
            content = f.read()

        self.assertIn('There is no supported `install.sh`', content)
        self.assertIn('python bin/chat-room.py', content)
        self.assertIn('python src/python/runserver_refactored.py test', content)
        self.assertIn('./compose-up.sh', content)

    def test_readme_points_to_current_setup_paths(self):
        with open(self.readme, 'r') as f:
            content = f.read()

        self.assertIn('docs/setup/INSTALL.md', content)
        self.assertIn('QUICKSTART.md', content)
        self.assertIn('bin/chat-room.py', content)
        self.assertNotIn('./install.sh', content.lower())


if __name__ == '__main__':
    unittest.main()
