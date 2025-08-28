#!/usr/bin/env python3
"""
Simple integration test for AEGIS CLI components.
Tests that all CLI commands can be invoked without errors.
"""

import subprocess
import sys
import os
import tempfile
import shutil
from pathlib import Path


def run_command(cmd, expect_success=True, timeout=30):
    """Run a CLI command and return result."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        if expect_success and result.returncode != 0:
            print(f"❌ Command failed with exit code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

        print(f"✅ Command completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout[:200]}...")

        return True

    except subprocess.TimeoutExpired:
        print(f"⏰ Command timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"❌ Command failed with exception: {e}")
        return False


def test_cli_commands():
    """Test basic CLI command functionality."""
    print("🧪 Testing AEGIS CLI Integration")
    print("=" * 50)

    # Test basic commands that should work without dependencies
    basic_commands = [
        (["python", "main.py", "--help"], "Help command"),
        (["python", "main.py", "version"], "Version command"),
        (["python", "main.py", "config", "--help"], "Config help"),
        (["python", "main.py", "run", "--help"], "Run help"),
        (["python", "main.py", "discover", "--help"], "Discover help"),
        (["python", "main.py", "questionnaire", "--help"], "Questionnaire help"),
        (["python", "main.py", "catalog", "--help"], "Catalog help"),
        (["python", "main.py", "recommend", "--help"], "Recommend help"),
        (["python", "main.py", "validate", "--help"], "Validate help"),
    ]

    success_count = 0
    total_count = len(basic_commands)

    for cmd, description in basic_commands:
        print(f"\n📋 Testing: {description}")
        if run_command(cmd, expect_success=True, timeout=10):
            success_count += 1
        else:
            print(f"❌ Failed: {description}")

    # Test config initialization
    print(f"\n📋 Testing: Config initialization")
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = os.path.join(temp_dir, "test-config.yaml")
        cmd = ["python", "main.py", "config", "--init"]

        # Change to temp directory for this test
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            if run_command(cmd, expect_success=True, timeout=10):
                success_count += 1
                total_count += 1

                # Check if config file was created
                if os.path.exists("aegis-config.yaml"):
                    print("✅ Config file created successfully")
                else:
                    print("⚠️  Config file not found, but command succeeded")
            else:
                total_count += 1
        finally:
            os.chdir(original_cwd)

    # Test run command without --all (should show help)
    print(f"\n📋 Testing: Run command help display")
    if run_command(["python", "main.py", "run"], expect_success=True, timeout=10):
        success_count += 1
    total_count += 1

    # Summary
    print(f"\n" + "=" * 50)
    print(f"🎯 Test Results: {success_count}/{total_count} commands successful")

    if success_count == total_count:
        print("🎉 All CLI integration tests passed!")
        return True
    else:
        print(f"⚠️  {total_count - success_count} tests failed")
        return False


def test_error_handling():
    """Test CLI error handling."""
    print(f"\n🧪 Testing Error Handling")
    print("=" * 30)

    # Test commands that should fail gracefully
    error_commands = [
        (
            ["python", "main.py", "discover", "--context", "nonexistent"],
            "Invalid context",
        ),
        (
            ["python", "main.py", "questionnaire", "--input", "nonexistent.yaml"],
            "Missing input file",
        ),
        (
            ["python", "main.py", "recommend", "--input", "nonexistent.yaml"],
            "Missing cluster data",
        ),
        (
            ["python", "main.py", "validate", "--directory", "nonexistent"],
            "Missing directory",
        ),
    ]

    success_count = 0

    for cmd, description in error_commands:
        print(f"\n📋 Testing error handling: {description}")
        # These should fail, but gracefully (exit code 1, not crash)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )

            if result.returncode == 1:  # Expected failure
                print("✅ Command failed gracefully as expected")
                success_count += 1
            elif result.returncode == 0:
                print("⚠️  Command succeeded unexpectedly")
            else:
                print(
                    f"⚠️  Command failed with unexpected exit code: {result.returncode}"
                )

        except subprocess.TimeoutExpired:
            print("⏰ Command timed out")
        except Exception as e:
            print(f"❌ Command crashed: {e}")

    print(
        f"\n🎯 Error Handling Results: {success_count}/{len(error_commands)} handled gracefully"
    )
    return success_count == len(error_commands)


if __name__ == "__main__":
    print("🚀 AEGIS CLI Integration Test Suite")
    print("=" * 60)

    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ Error: main.py not found. Please run from aegis directory.")
        sys.exit(1)

    # Run tests
    cli_success = test_cli_commands()
    error_success = test_error_handling()

    print(f"\n" + "=" * 60)
    print(f"📊 Final Results:")
    print(f"   • CLI Commands: {'✅ PASS' if cli_success else '❌ FAIL'}")
    print(f"   • Error Handling: {'✅ PASS' if error_success else '❌ FAIL'}")

    if cli_success and error_success:
        print(f"\n🎉 All integration tests passed!")
        print(f"💡 AEGIS CLI is ready for use!")
        sys.exit(0)
    else:
        print(f"\n⚠️  Some tests failed. Please check the output above.")
        sys.exit(1)
