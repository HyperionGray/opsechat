#!/usr/bin/env python3
"""
Tests for installer scripts

This module tests basic functionality of the install.sh and uninstall.sh scripts.
"""

import os
import subprocess
import unittest


class TestInstallerScripts(unittest.TestCase):
    """Test cases for installer scripts"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.install_script = os.path.join(self.repo_root, 'install.sh')
        self.uninstall_script = os.path.join(self.repo_root, 'uninstall.sh')
    
    def test_install_script_exists(self):
        """Test that install.sh exists"""
        self.assertTrue(os.path.exists(self.install_script),
                       "install.sh should exist in repository root")
    
    def test_install_script_executable(self):
        """Test that install.sh is executable"""
        self.assertTrue(os.access(self.install_script, os.X_OK),
                       "install.sh should be executable")
    
    def test_uninstall_script_exists(self):
        """Test that uninstall.sh exists"""
        self.assertTrue(os.path.exists(self.uninstall_script),
                       "uninstall.sh should exist in repository root")
    
    def test_uninstall_script_executable(self):
        """Test that uninstall.sh is executable"""
        self.assertTrue(os.access(self.uninstall_script, os.X_OK),
                       "uninstall.sh should be executable")
    
    def test_install_script_syntax(self):
        """Test that install.sh has valid bash syntax"""
        result = subprocess.run(
            ['bash', '-n', self.install_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0,
                        f"install.sh should have valid bash syntax. Error: {result.stderr}")
    
    def test_uninstall_script_syntax(self):
        """Test that uninstall.sh has valid bash syntax"""
        result = subprocess.run(
            ['bash', '-n', self.uninstall_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0,
                        f"uninstall.sh should have valid bash syntax. Error: {result.stderr}")
    
    def test_install_script_has_shebang(self):
        """Test that install.sh has proper shebang"""
        with open(self.install_script, 'r') as f:
            first_line = f.readline().strip()
        self.assertEqual(first_line, '#!/bin/bash',
                        "install.sh should have #!/bin/bash shebang")
    
    def test_uninstall_script_has_shebang(self):
        """Test that uninstall.sh has proper shebang"""
        with open(self.uninstall_script, 'r') as f:
            first_line = f.readline().strip()
        self.assertEqual(first_line, '#!/bin/bash',
                        "uninstall.sh should have #!/bin/bash shebang")
    
    def test_install_script_has_error_handling(self):
        """Test that install.sh has set -e for error handling"""
        with open(self.install_script, 'r') as f:
            content = f.read()
        self.assertIn('set -e', content,
                     "install.sh should have 'set -e' for error handling")
    
    def test_install_script_functions(self):
        """Test that install.sh has required functions"""
        with open(self.install_script, 'r') as f:
            content = f.read()
        
        required_functions = [
            'detect_os()',
            'install_python()',
            'install_tor()',
            'configure_tor()',
            'setup_repository()',
            'setup_virtualenv()',
            'install_python_dependencies()',
            'verify_installation()',
            'main()'
        ]
        
        for func in required_functions:
            self.assertIn(func, content,
                         f"install.sh should have {func} function")
    
    def test_uninstall_script_functions(self):
        """Test that uninstall.sh has required functions"""
        with open(self.uninstall_script, 'r') as f:
            content = f.read()
        
        required_functions = [
            'confirm_uninstall()',
            'stop_processes()',
            'remove_installation()',
            'verify_uninstall()',
            'main()'
        ]
        
        for func in required_functions:
            self.assertIn(func, content,
                         f"uninstall.sh should have {func} function")
    
    def test_install_script_package_managers(self):
        """Test that install.sh supports multiple package managers"""
        with open(self.install_script, 'r') as f:
            content = f.read()
        
        package_managers = ['apt', 'yum', 'dnf', 'pacman']
        
        for pm in package_managers:
            self.assertIn(pm, content,
                         f"install.sh should support {pm} package manager")
    
    def test_install_documentation_exists(self):
        """Test that INSTALL.md documentation exists"""
        install_doc = os.path.join(self.repo_root, 'INSTALL.md')
        self.assertTrue(os.path.exists(install_doc),
                       "INSTALL.md should exist in repository root")
    
    def test_readme_has_install_section(self):
        """Test that README.md references the installer"""
        readme = os.path.join(self.repo_root, 'README.md')
        with open(readme, 'r') as f:
            content = f.read()
        
        self.assertIn('install.sh', content.lower(),
                     "README.md should reference install.sh")


if __name__ == '__main__':
    unittest.main()
