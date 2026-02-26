#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for main.py CLI entry point.

This script tests all the functionality of the main.py CLI interface
to ensure it works correctly and handles errors gracefully.
"""

import subprocess
import sys
import os
from pathlib import Path


class CLITester:
    """Test harness for the main.py CLI interface."""
    
    def __init__(self):
        """Initialize the tester."""
        self.test_count = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.project_root = Path(__file__).parent
    
    def run_cli_command(self, args, timeout=10):
        """
        Run a CLI command and capture output.
        
        Args:
            args (list): Command arguments
            timeout (int): Timeout in seconds
            
        Returns:
            tuple: (return_code, stdout, stderr)
        """
        try:
            cmd = [sys.executable, "main.py"] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
                encoding='utf-8',
                errors='replace'
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -2, "", str(e)
    
    def test_case(self, name, test_func):
        """
        Run a single test case.
        
        Args:
            name (str): Test name
            test_func (callable): Test function that returns bool
        """
        self.test_count += 1
        print(f"\nTest {self.test_count}: {name}")
        
        try:
            if test_func():
                print("PASSED")
                self.passed_tests += 1
            else:
                print("FAILED")
                self.failed_tests += 1
        except Exception as e:
            print(f"FAILED with exception: {e}")
            self.failed_tests += 1
    
    def test_no_args(self):
        """Test running main.py with no arguments."""
        returncode, stdout, stderr = self.run_cli_command([])
        
        # Should return 0 (success) and show usage instructions
        if returncode != 0:
            print(f"   Expected returncode 0, got {returncode}")
            return False
        
        # Should contain key elements of usage instructions
        required_strings = [
            "Calliope IDE",
            "Getting Started",
            "python main.py start",
            "npm run dev",
            "Available Commands"
        ]
        
        for required_str in required_strings:
            if required_str not in stdout:
                print(f"   Missing required string: '{required_str}'")
                return False
        
        print("   Shows usage instructions correctly")
        return True
    
    def test_help_flag(self):
        """Test running main.py --help."""
        returncode, stdout, stderr = self.run_cli_command(["--help"])
        
        # Should return 0 and show help
        if returncode != 0:
            print(f"   Expected returncode 0, got {returncode}")
            return False
        
        # Should contain argparse help elements
        required_strings = [
            "usage:",
            "Calliope IDE",
            "start",
            "backend",
            "Examples:"
        ]
        
        for required_str in required_strings:
            if required_str not in stdout:
                print(f"   Missing required string: '{required_str}'")
                return False
        
        print("   Shows help information correctly")
        return True
    
    def test_version_flag(self):
        """Test running main.py --version."""
        returncode, stdout, stderr = self.run_cli_command(["--version"])
        
        # Should return 0 and show version
        if returncode != 0:
            print(f"   Expected returncode 0, got {returncode}")
            return False
        
        if "Calliope IDE v" not in stdout:
            print("   Version string not found in output")
            return False
        
        print("   Shows version correctly")
        return True
    
    def test_invalid_command(self):
        """Test running main.py with invalid command."""
        returncode, stdout, stderr = self.run_cli_command(["invalid"])
        
        # Should return non-zero (error)
        if returncode == 0:
            print("   Expected non-zero returncode for invalid command")
            return False
        
        # Should show error message about invalid choice
        if "invalid choice" not in stderr and "invalid choice" not in stdout:
            print("   Should show invalid choice error")
            return False
        
        print("   Handles invalid commands correctly")
        return True
    
    def test_dependency_checks(self):
        """Test that dependency checking works."""
        # Test by running start command with short timeout
        returncode, stdout, stderr = self.run_cli_command(["start"], timeout=5)
        
        # The command should either:
        # 1. Start successfully and then timeout (return -1)
        # 2. Fail due to missing dependencies (return 1)
        # 3. Fail due to missing server files (return 1)
        
        valid_returncodes = [-1, 0, 1]
        if returncode not in valid_returncodes:
            print(f"   Unexpected returncode: {returncode}")
            return False
        
        # Check that dependency checking output appears
        dependency_indicators = [
            "Checking backend dependencies",
            "Missing dependency",
            "Backend server file not found",
            "Starting Calliope IDE Backend Server",
            "All backend dependencies are installed"
        ]
        
        found_indicator = any(indicator in stdout for indicator in dependency_indicators)
        if not found_indicator:
            print("   No dependency checking indicators found")
            print(f"   stdout preview: {stdout[:200]}...")
            return False
        
        print("   Dependency checking functionality works")
        return True
    
    def test_backend_command(self):
        """Test that backend command works (alias for start)."""
        returncode, stdout, stderr = self.run_cli_command(["backend"], timeout=5)
        
        # Should behave the same as start command
        valid_returncodes = [-1, 0, 1]
        if returncode not in valid_returncodes:
            print(f"   Unexpected returncode: {returncode}")
            return False
        
        dependency_indicators = [
            "Checking backend dependencies",
            "Missing dependency",
            "Backend server file not found",
            "Starting Calliope IDE Backend Server",
            "All backend dependencies are installed"
        ]
        
        found_indicator = any(indicator in stdout for indicator in dependency_indicators)
        if not found_indicator:
            print("   Backend command doesn't seem to work like start command")
            return False
        
        print("   Backend command works correctly")
        return True
    
    def test_file_content_validation(self):
        """Test that the main.py file has proper structure."""
        main_py_path = self.project_root / "main.py"
        if not main_py_path.exists():
            print("   main.py file not found")
            return False
        
        try:
            main_py_content = main_py_path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"   Could not read main.py: {e}")
            return False
        
        # Check for essential components
        required_patterns = [
            "KeyboardInterrupt",
            "argparse",
            "def main(",
            "if __name__ == \"__main__\":",
            "check_backend_dependencies",
            "start_backend_server",
        ]
        
        for pattern in required_patterns:
            if pattern not in main_py_content:
                print(f"   Missing required code pattern: {pattern}")
                return False
        
        print("   File structure validation passed")
        return True
    
    def run_all_tests(self):
        """Run all tests and report results."""
        print("=" * 70)
        print("CLI Entry Point Test Suite")
        print("=" * 70)
        
        # Run all test cases
        self.test_case("No arguments (usage instructions)", self.test_no_args)
        self.test_case("Help flag (--help)", self.test_help_flag)
        self.test_case("Version flag (--version)", self.test_version_flag)
        self.test_case("Invalid command handling", self.test_invalid_command)
        self.test_case("Dependency checking functionality", self.test_dependency_checks)
        self.test_case("Backend command (alias)", self.test_backend_command)
        self.test_case("File structure validation", self.test_file_content_validation)
        
        # Print summary
        print("\n" + "=" * 70)
        print("Test Results Summary")
        print("=" * 70)
        print(f"Total tests:  {self.test_count}")
        print(f"Passed:       {self.passed_tests}")
        print(f"Failed:       {self.failed_tests}")
        
        if self.failed_tests == 0:
            print("\nAll tests passed! The CLI is working correctly.")
            print("=" * 70)
            return 0
        else:
            print(f"\n{self.failed_tests} test(s) failed. Please review the implementation.")
            print("=" * 70)
            return 1


def main():
    """Main test function."""
    tester = CLITester()
    return tester.run_all_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)