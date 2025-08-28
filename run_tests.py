#!/usr/bin/env python3
"""
Comprehensive test runner for AEGIS.
Runs all test suites and generates coverage reports.
"""

import subprocess
import sys
import os
import time
from pathlib import Path


def run_command(cmd, description, timeout=60):
    """Run a command and return success status."""
    print(f"\n🧪 {description}")
    print(f"Running: {' '.join(cmd)}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} passed ({duration:.1f}s)")
            if result.stdout:
                # Show summary line for pytest
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'passed' in line and ('failed' in line or 'error' in line or '=' in line):
                        print(f"   {line}")
                        break
            return True
        else:
            print(f"❌ {description} failed ({duration:.1f}s)")
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        return False


def main():
    """Run comprehensive test suite."""
    print("🚀 AEGIS Comprehensive Test Suite")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ Error: main.py not found. Please run from aegis directory.")
        sys.exit(1)
    
    # Test categories
    test_suites = [
        # Unit tests
        {
            "name": "Unit Tests - Core Components",
            "commands": [
                (["python", "-m", "pytest", "tests/test_config.py", "-v"], "Configuration Tests"),
                (["python", "-m", "pytest", "tests/test_discovery.py", "-v"], "Discovery Tests"),
                (["python", "-m", "pytest", "tests/test_questionnaire.py", "-v"], "Questionnaire Tests"),
                (["python", "-m", "pytest", "tests/test_catalog.py", "-v"], "Catalog Tests"),
            ]
        },
        {
            "name": "Unit Tests - AI Components", 
            "commands": [
                (["python", "-m", "pytest", "tests/test_ai_selector.py", "-v"], "AI Selector Tests"),
                (["python", "-m", "pytest", "tests/test_bedrock_client.py", "-v"], "Bedrock Client Tests"),
                (["python", "-m", "pytest", "tests/test_kyverno_validator.py", "-v"], "Kyverno Validator Tests"),
                (["python", "-m", "pytest", "tests/test_output_manager.py", "-v"], "Output Manager Tests"),
            ]
        },
        {
            "name": "Integration Tests",
            "commands": [
                (["python", "-m", "pytest", "tests/integration/test_end_to_end.py", "-v"], "End-to-End Tests"),
                (["python", "-m", "pytest", "tests/integration/test_external_services.py", "-v", "-m", "not integration"], "Mocked External Service Tests"),
            ]
        },
        {
            "name": "CLI Integration Tests",
            "commands": [
                (["python", "test_cli_integration.py"], "CLI Integration Tests"),
            ]
        }
    ]
    
    # Coverage test
    coverage_commands = [
        {
            "name": "Test Coverage Analysis",
            "commands": [
                (["python", "-m", "pytest", "tests/", "--cov=.", "--cov-report=term-missing", "--cov-report=html"], "Coverage Report Generation"),
            ]
        }
    ]
    
    # Run all test suites
    total_passed = 0
    total_failed = 0
    
    for suite in test_suites:
        print(f"\n📦 {suite['name']}")
        print("-" * 40)
        
        suite_passed = 0
        suite_failed = 0
        
        for cmd, description in suite['commands']:
            if run_command(cmd, description, timeout=120):
                suite_passed += 1
                total_passed += 1
            else:
                suite_failed += 1
                total_failed += 1
        
        print(f"\n📊 {suite['name']} Results: {suite_passed} passed, {suite_failed} failed")
    
    # Run coverage analysis if all tests passed
    if total_failed == 0:
        print(f"\n🎯 All tests passed! Running coverage analysis...")
        
        for suite in coverage_commands:
            print(f"\n📦 {suite['name']}")
            print("-" * 40)
            
            for cmd, description in suite['commands']:
                run_command(cmd, description, timeout=180)
    
    # Final summary
    print(f"\n" + "=" * 60)
    print(f"📊 Final Test Results:")
    print(f"   • Total Tests: {total_passed + total_failed}")
    print(f"   • Passed: {total_passed}")
    print(f"   • Failed: {total_failed}")
    print(f"   • Success Rate: {(total_passed / (total_passed + total_failed) * 100):.1f}%")
    
    if total_failed == 0:
        print(f"\n🎉 All tests passed! AEGIS is ready for deployment!")
        print(f"📄 Coverage report available at: htmlcov/index.html")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total_failed} test(s) failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()