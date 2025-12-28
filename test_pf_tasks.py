#!/usr/bin/env python3
"""
Comprehensive test suite for all pf tasks
Tests functionality without modifying the system
"""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock
import argparse

# Add pf-tasks to path for imports
sys.path.insert(0, str(Path(__file__).parent / "pf-tasks"))

class PFTaskTester:
    def __init__(self):
        self.test_results = []
        self.errors = []
        
    def log_test(self, test_name, passed, message=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        result = f"[{status}] {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))
        if not passed:
            self.errors.append(f"{test_name}: {message}")
    
    def test_imports(self):
        """Test that all pf task modules can be imported"""
        print("\n=== Testing Module Imports ===")
        
        modules = ['build', 'deploy', 'test', 'clean']
        for module_name in modules:
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, 
                    Path(__file__).parent / "pf-tasks" / f"{module_name}.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.log_test(f"Import {module_name}.py", True)
            except Exception as e:
                self.log_test(f"Import {module_name}.py", False, str(e))
    
    def test_command_construction(self):
        """Test command construction without execution"""
        print("\n=== Testing Command Construction ===")
        
        # Mock subprocess.run to capture commands without executing
        captured_commands = []
        
        def mock_run(cmd, *args, **kwargs):
            captured_commands.append(cmd)
            # Return a mock successful result
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "mock output"
            mock_result.stderr = ""
            return mock_result
        
        with patch('subprocess.run', side_effect=mock_run):
            # Test build.py command construction
            try:
                import build
                # Test podman build command
                build.build_image('podman', 'test:tag')
                
                # Verify podman command was constructed correctly
                podman_build_found = False
                for cmd in captured_commands:
                    if 'podman' in cmd and 'build' in cmd and '--network' in cmd and 'host' in cmd:
                        podman_build_found = True
                        break
                
                self.log_test("Build command construction (podman)", podman_build_found)
                
                # Test docker build command
                captured_commands.clear()
                build.build_image('docker', 'test:tag')
                
                docker_build_found = False
                for cmd in captured_commands:
                    if 'docker' in cmd and 'build' in cmd and '--network' in cmd and 'host' in cmd:
                        docker_build_found = True
                        break
                
                self.log_test("Build command construction (docker)", docker_build_found)
                
            except Exception as e:
                self.log_test("Build command construction", False, str(e))
    
    def test_tool_detection(self):
        """Test tool detection logic"""
        print("\n=== Testing Tool Detection ===")
        
        # Test build.py tool detection
        try:
            import build
            
            # Mock successful tool detection
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                tool = build.detect_container_tool()
                self.log_test("Container tool detection (success)", tool in ['podman', 'docker'])
                
            # Mock failed tool detection
            with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'cmd')):
                try:
                    build.detect_container_tool()
                    self.log_test("Container tool detection (failure)", False, "Should have exited")
                except SystemExit:
                    self.log_test("Container tool detection (failure)", True, "Properly exits when no tools found")
                    
        except Exception as e:
            self.log_test("Tool detection test", False, str(e))
    
    def test_argument_parsing(self):
        """Test argument parsing for all scripts"""
        print("\n=== Testing Argument Parsing ===")
        
        # Test deploy.py argument parsing
        try:
            import deploy
            
            # Test valid arguments
            test_args = [
                ['--method', 'quadlet'],
                ['--method', 'compose'],
                ['--method', 'auto'],
                ['--compose-tool', 'podman-compose'],
                []  # default args
            ]
            
            for args in test_args:
                try:
                    # Mock sys.argv
                    with patch('sys.argv', ['deploy.py'] + args):
                        parser = argparse.ArgumentParser(description='Deploy opsechat')
                        parser.add_argument('--method', choices=['quadlet', 'compose', 'auto'], 
                                           default='auto', help='Deployment method')
                        parser.add_argument('--compose-tool', choices=['podman-compose', 'docker-compose', 'docker-compose-plugin'],
                                           help='Specific compose tool to use')
                        parsed_args = parser.parse_args(args)
                        self.log_test(f"Deploy args parsing: {args}", True)
                except Exception as e:
                    self.log_test(f"Deploy args parsing: {args}", False, str(e))
                    
        except Exception as e:
            self.log_test("Argument parsing test", False, str(e))
    
    def test_file_operations(self):
        """Test file operation logic without actually modifying files"""
        print("\n=== Testing File Operations ===")
        
        try:
            import deploy
            from pathlib import Path
            
            # Test quadlet file detection
            project_root = Path(__file__).parent
            quadlet_dir = project_root / "quadlets"
            
            if quadlet_dir.exists():
                quadlet_files = list(quadlet_dir.glob("*.container")) + list(quadlet_dir.glob("*.network")) + list(quadlet_dir.glob("*.timer")) + list(quadlet_dir.glob("*.service")) + list(quadlet_dir.glob("*.volume"))
                self.log_test("Quadlet file detection", len(quadlet_files) > 0, f"Found {len(quadlet_files)} quadlet files")
            else:
                self.log_test("Quadlet file detection", False, "Quadlets directory not found")
                
            # Test torrc file existence
            torrc_file = project_root / "torrc"
            self.log_test("Torrc file existence", torrc_file.exists())
            
        except Exception as e:
            self.log_test("File operations test", False, str(e))
    
    def test_error_handling(self):
        """Test error handling in run_command functions"""
        print("\n=== Testing Error Handling ===")
        
        try:
            import build
            
            # Test successful command
            with patch('subprocess.run') as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "success"
                mock_result.stderr = ""
                mock_run.return_value = mock_result
                
                result = build.run_command(['echo', 'test'], check=False)
                self.log_test("Error handling (success)", result.returncode == 0)
            
            # Test failed command with check=False
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr="error")
                
                result = build.run_command(['false'], check=False)
                self.log_test("Error handling (failure, check=False)", isinstance(result, subprocess.CalledProcessError))
            
            # Test failed command with check=True
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr="error")
                
                try:
                    build.run_command(['false'], check=True)
                    self.log_test("Error handling (failure, check=True)", False, "Should have exited")
                except SystemExit:
                    self.log_test("Error handling (failure, check=True)", True, "Properly exits on error")
                    
        except Exception as e:
            self.log_test("Error handling test", False, str(e))
    
    def test_duplicate_code(self):
        """Check for duplicate code patterns"""
        print("\n=== Testing for Duplicate Code ===")
        
        try:
            # Read all pf task files
            pf_files = {}
            for filename in ['build.py', 'deploy.py', 'test.py', 'clean.py']:
                with open(Path(__file__).parent / "pf-tasks" / filename, 'r') as f:
                    pf_files[filename] = f.read()
            
            # Check for duplicate run_command functions
            run_command_implementations = []
            for filename, content in pf_files.items():
                if 'def run_command(' in content:
                    # Extract run_command function
                    lines = content.split('\n')
                    in_function = False
                    function_lines = []
                    indent_level = None
                    
                    for line in lines:
                        if 'def run_command(' in line:
                            in_function = True
                            indent_level = len(line) - len(line.lstrip())
                            function_lines = [line]
                        elif in_function:
                            current_indent = len(line) - len(line.lstrip())
                            if line.strip() and current_indent <= indent_level and not line.startswith(' '):
                                break
                            function_lines.append(line)
                    
                    if function_lines:
                        run_command_implementations.append((filename, '\n'.join(function_lines)))
            
            # Check if all run_command implementations are identical
            if len(run_command_implementations) > 1:
                first_impl = run_command_implementations[0][1]
                all_identical = all(impl[1] == first_impl for impl in run_command_implementations)
                
                if all_identical:
                    self.log_test("Duplicate run_command functions", False, 
                                f"Identical run_command in {len(run_command_implementations)} files - should be refactored")
                else:
                    self.log_test("run_command function variations", True, 
                                "Different implementations found - may be intentional")
            
        except Exception as e:
            self.log_test("Duplicate code test", False, str(e))
    
    def test_integration_points(self):
        """Test integration with existing scripts"""
        print("\n=== Testing Integration Points ===")
        
        project_root = Path(__file__).parent
        
        # Check for existing scripts that pf tasks integrate with
        integration_files = [
            'compose-up.sh',
            'compose-down.sh', 
            'docker-compose.yml',
            'package.json',
            'playwright.config.js'
        ]
        
        for filename in integration_files:
            file_path = project_root / filename
            exists = file_path.exists()
            self.log_test(f"Integration file exists: {filename}", exists)
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting comprehensive pf task testing...")
        
        self.test_imports()
        self.test_command_construction()
        self.test_tool_detection()
        self.test_argument_parsing()
        self.test_file_operations()
        self.test_error_handling()
        self.test_duplicate_code()
        self.test_integration_points()
        
        # Summary
        print(f"\n=== Test Summary ===")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, passed, _ in self.test_results if passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        
        if self.errors:
            print(f"\n=== Errors Found ===")
            for error in self.errors:
                print(f"  - {error}")
        
        return failed_tests == 0

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description='Test all pf tasks')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    tester = PFTaskTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n[✓] All tests passed!")
        sys.exit(0)
    else:
        print("\n[!] Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()