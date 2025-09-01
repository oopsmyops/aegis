"""
Kyverno policy validation system for AEGIS.
Executes Kyverno CLI tests and generates YAML reports with AI-powered fixing.
"""

import os
import json
import yaml
import logging
import subprocess
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from models import RecommendedPolicy, PolicyCatalogEntry
from interfaces import PolicyValidatorInterface
from exceptions import ValidationError
from ai.bedrock_client import BedrockClient
from ai.test_case_generator import TestCaseGenerator


@dataclass
class ValidationResult:
    """Result of policy validation with comprehensive details."""

    policy_name: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    test_results: Dict[str, Any] = field(default_factory=dict)
    fixed_content: Optional[str] = None
    generated_tests: bool = False
    validation_report: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML report."""
        return {
            "policy_name": self.policy_name,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "test_results": self.test_results,
            "has_fixes": bool(self.fixed_content),
            "generated_tests": self.generated_tests,
            "validation_report": self.validation_report,
        }


class KyvernoValidator(PolicyValidatorInterface):
    """
    Validates Kyverno policies using CLI and provides AI-powered fixing.

    Key Features:
    - Executes Kyverno CLI tests and generates YAML reports
    - AI-powered fixing of failing test cases
    - AI-powered test case generation for policies missing tests
    - Comprehensive validation reporting
    """

    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        enable_ai_fixes: bool = False,
    ):
        """Initialize Kyverno validator."""
        self.bedrock_client = bedrock_client
        self.test_case_generator = (
            TestCaseGenerator(bedrock_client) if bedrock_client else None
        )
        self.enable_ai_fixes = enable_ai_fixes
        self.logger = logging.getLogger(__name__)
        self.kyverno_command = "kyverno"  # Add this for test compatibility
        self.kyverno_cli_available = self._check_kyverno_cli()

        # Track validation statistics
        self.validation_stats = {
            "total_policies": 0,
            "passed": 0,
            "failed": 0,
            "fixed": 0,
            "tests_generated": 0,
        }

    def validate_policies_with_report(
        self, policies: List[RecommendedPolicy], output_dir: str
    ) -> Tuple[List[ValidationResult], str]:
        """
        Validate multiple policies and generate comprehensive YAML report.

        Args:
            policies: List of recommended policies to validate
            output_dir: Directory containing organized policy files

        Returns:
            Tuple of (validation_results, report_file_path)
        """
        self.logger.info(f"Starting validation of {len(policies)} policies")
        self.validation_stats["total_policies"] = len(policies)

        validation_results = []

        # Run Kyverno CLI test on the entire output directory
        cli_report = self._execute_kyverno_cli_test(output_dir)

        # Process each policy
        for policy in policies:
            try:
                result = self._validate_single_policy(policy, output_dir, cli_report)
                validation_results.append(result)

                # Update statistics
                if result.passed:
                    self.validation_stats["passed"] += 1
                else:
                    self.validation_stats["failed"] += 1

                if result.fixed_content:
                    self.validation_stats["fixed"] += 1

                if result.generated_tests:
                    self.validation_stats["tests_generated"] += 1

            except Exception as e:
                self.logger.error(
                    f"Error validating policy {policy.original_policy.name}: {e}"
                )
                validation_results.append(
                    ValidationResult(
                        policy_name=policy.original_policy.name,
                        passed=False,
                        errors=[f"Validation error: {str(e)}"],
                    )
                )
                self.validation_stats["failed"] += 1

        # Generate YAML report
        report_file = self._generate_yaml_report(validation_results, output_dir)

        self.logger.info(f"Validation completed: {self.validation_stats}")
        return validation_results, report_file

    def _validate_single_policy(
        self, policy: RecommendedPolicy, output_dir: str, cli_report: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a single policy and apply fixes if enabled."""
        policy_name = policy.original_policy.name
        self.logger.info(f"Validating policy: {policy_name}")

        # Initialize result
        result = ValidationResult(policy_name=policy_name, passed=True)

        # Check if policy has test cases
        policy_dir = self._find_policy_directory(policy_name, output_dir)
        if not policy_dir:
            result.passed = False
            result.errors.append(f"Policy directory not found in {output_dir}")
            return result

        test_file = os.path.join(policy_dir, "kyverno-test.yaml")
        has_existing_tests = os.path.exists(test_file)

        # Generate test cases if missing and AI fixes are enabled
        if not has_existing_tests and self.enable_ai_fixes and self.test_case_generator:
            self.logger.info(f"Generating test cases for {policy_name}")
            try:
                test_content = (
                    self.test_case_generator.generate_comprehensive_test_case(
                        policy.customized_content, policy_name
                    )
                )

                # Write test file
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write(test_content)

                # Generate resource file if needed
                resource_file = os.path.join(policy_dir, "resource.yaml")
                if not os.path.exists(resource_file):
                    resource_content = self._generate_test_resources(policy)
                    with open(resource_file, "w", encoding="utf-8") as f:
                        f.write(resource_content)

                result.generated_tests = True
                result.warnings.append("Generated test cases using AI")

            except Exception as e:
                self.logger.error(
                    f"Failed to generate test cases for {policy_name}: {e}"
                )
                result.warnings.append(f"Could not generate test cases: {e}")

        # Store CLI output for Test Summary parsing - do this for ALL results
        if cli_report.get("stderr"):
            result.test_results["cli_stderr"] = cli_report["stderr"]
        if cli_report.get("full_output"):
            result.test_results["cli_full_output"] = cli_report["full_output"]
        if cli_report.get("json_output"):
            result.test_results["kyverno_json"] = cli_report["json_output"]
        if cli_report.get("test_errors"):
            result.test_results["test_errors"] = cli_report["test_errors"]

        # Extract validation results from CLI report
        policy_cli_result = self._extract_policy_result_from_cli(
            policy_name, cli_report
        )

        if policy_cli_result:
            result.passed = policy_cli_result.get("passed", False)
            result.errors.extend(policy_cli_result.get("errors", []))
            result.warnings.extend(policy_cli_result.get("warnings", []))
            self.logger.info(
                f"Policy {policy_name}: passed={result.passed}, errors={len(result.errors)}"
            )

            # Merge CLI results into test_results
            result.test_results.update(policy_cli_result)

            # Apply AI fixes if validation failed and fixes are enabled
            if not result.passed and self.enable_ai_fixes:
                result = self._apply_ai_fixes(result, policy, policy_dir)

            # Also check for test file errors and fix them if AI fixes are enabled
            if self.enable_ai_fixes and cli_report.get("test_errors"):
                result = self._fix_test_file_errors(
                    result, policy, policy_dir, cli_report["test_errors"]
                )

            # Handle test failures (when tests run but fail validation) if AI fixes are enabled
            if self.enable_ai_fixes and not result.passed and result.errors:
                self.logger.info(
                    f"Attempting to fix test failures for {result.policy_name}: passed={result.passed}, errors={len(result.errors)}"
                )
                result = self._fix_test_failures(result, policy, policy_dir, cli_report)
            elif self.enable_ai_fixes:
                self.logger.info(
                    f"Skipping test failure fix for {result.policy_name}: passed={result.passed}, errors={len(result.errors)}, ai_fixes={self.enable_ai_fixes}"
                )

        else:
            self.logger.info(f"Policy {policy_name}: No CLI result found")
            # No policy-specific CLI results available, but check if this policy failed in the global JSON
            if cli_report.get("json_output") and isinstance(
                cli_report["json_output"], list
            ):
                for failure in cli_report["json_output"]:
                    if (
                        isinstance(failure, dict)
                        and failure.get("POLICY") == policy_name
                    ):
                        result.passed = False
                        result.errors.append(
                            f"Policy failure: {failure.get('REASON', 'Unknown failure')}"
                        )
                        break

            if not result.errors:
                result.warnings.append("No Kyverno CLI results available")
                if not self.kyverno_cli_available:
                    result.warnings.append("Kyverno CLI not available")

        # Create validation report for this policy
        result.validation_report = {
            "timestamp": datetime.now().isoformat(),
            "kyverno_cli_available": self.kyverno_cli_available,
            "has_existing_tests": has_existing_tests,
            "ai_fixes_enabled": self.enable_ai_fixes,
            "policy_directory": policy_dir,
        }

        return result

    def _apply_ai_fixes(
        self, result: ValidationResult, policy: RecommendedPolicy, policy_dir: str
    ) -> ValidationResult:
        """Apply AI-powered fixes to failing test cases."""
        if not self.bedrock_client:
            result.warnings.append("AI fixes requested but no Bedrock client available")
            return result

        self.logger.info(f"Applying AI fixes for {result.policy_name}")

        try:
            # Analyze the validation errors
            error_analysis = self._analyze_validation_errors(
                result.errors, policy.customized_content
            )

            # Generate fixes based on error analysis
            fixes_applied = []

            # Fix test cases (not policy content - policies remain unchanged)
            test_file = os.path.join(policy_dir, "kyverno-test.yaml")
            if os.path.exists(test_file):
                fixed_test = self._fix_test_case_with_ai(
                    test_file, result.errors, policy.customized_content
                )
                if fixed_test:
                    with open(test_file, "w", encoding="utf-8") as f:
                        f.write(fixed_test)
                    fixes_applied.append("Fixed test case")

            # Generate missing resource files
            resource_file = os.path.join(policy_dir, "resource.yaml")
            if (
                not os.path.exists(resource_file)
                or "no such file" in str(result.errors).lower()
            ):
                resource_content = self._generate_test_resources_with_ai(
                    policy, error_analysis
                )
                with open(resource_file, "w", encoding="utf-8") as f:
                    f.write(resource_content)
                fixes_applied.append("Generated resource file")

            if fixes_applied:
                result.fixed_content = "AI fixes applied to test cases"
                result.warnings.extend([f"AI fix: {fix}" for fix in fixes_applied])
                self.logger.info(
                    f"Applied AI fixes for {result.policy_name}: {fixes_applied}"
                )

        except Exception as e:
            self.logger.error(f"Error applying AI fixes for {result.policy_name}: {e}")
            result.warnings.append(f"AI fix failed: {e}")

        return result

    def _execute_kyverno_cli_test(self, output_dir: str) -> Dict[str, Any]:
        """Execute Kyverno CLI test on the output directory and return results."""
        if not self.kyverno_cli_available:
            self.logger.warning("Kyverno CLI not available")
            return {
                "available": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Kyverno CLI not available",
                "passed": False,
            }

        try:
            self.logger.info(f"Running Kyverno CLI test on {output_dir}")

            # Run kyverno test command with JSON output for reliable parsing
            result = subprocess.run(
                [
                    "kyverno",
                    "test",
                    output_dir,
                    "--require-tests",
                    "--fail-only",
                    "-ojson",
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=None,
            )

            # Parse JSON output from both stdout and stderr
            # Kyverno can output JSON to either stdout or stderr depending on version and flags
            json_output = None
            combined_output = result.stdout + "\n" + result.stderr

            # Look for JSON in the combined output
            import re

            # Look for JSON array pattern that can span multiple lines
            json_match = re.search(r"\[\s*\{.*?\}\s*\]", combined_output, re.DOTALL)
            if json_match:
                json_line = json_match.group(0)
                try:
                    json_output = json.loads(json_line)
                    self.logger.info(
                        f"Successfully parsed Kyverno JSON output with {len(json_output)} failure(s)"
                    )
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse Kyverno JSON output: {e}")
                    self.logger.debug(f"JSON line: {json_line[:200]}")
                    json_output = {"raw_output": json_line, "parse_error": str(e)}
            else:
                # Look for single-line JSON patterns
                for line in combined_output.split("\n"):
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]") and "{" in line:
                        try:
                            json_output = json.loads(line)
                            self.logger.info(
                                f"Successfully parsed Kyverno JSON output with {len(json_output)} failure(s)"
                            )
                            break
                        except json.JSONDecodeError:
                            continue

                if not json_output:
                    # Check if we have any failures indicated by return code
                    if result.returncode != 0 and (
                        "failed" in result.stderr.lower()
                        or "error" in result.stderr.lower()
                    ):
                        self.logger.info(
                            "Kyverno CLI indicated failures but no JSON found"
                        )
                        json_output = {"no_json_found": True, "has_failures": True}
                    else:
                        # No failures found
                        self.logger.info("No Kyverno test failures found")
                        json_output = None

            # Capture both stdout and stderr for Test Summary parsing
            full_output = result.stdout + "\n" + result.stderr

            # Check for test file errors in stdout (Kyverno outputs test errors to stdout)
            test_errors = []
            if result.stdout and "Test errors:" in result.stdout:
                stdout_lines = result.stdout.split("\n")
                current_error = None
                collecting_error = False

                for line in stdout_lines:
                    line = line.strip()
                    if line.startswith("Path:"):
                        # Save previous error if exists
                        if current_error:
                            test_errors.append(current_error)
                        # Start new error
                        current_error = {
                            "path": line.replace("Path:", "").strip(),
                            "error": "",
                        }
                        collecting_error = False
                    elif line.startswith("Error:") and current_error:
                        current_error["error"] = line.replace("Error:", "").strip()
                        collecting_error = True
                    elif (
                        collecting_error
                        and current_error
                        and line
                        and not line.startswith("Error:")
                        and not line.startswith("Path:")
                    ):
                        # Continue collecting multi-line error message
                        if current_error["error"]:
                            current_error["error"] += " " + line
                        else:
                            current_error["error"] = line
                    elif (
                        line.startswith("Error:")
                        and "found" in line
                        and "errors after loading tests" in line
                    ):
                        # This is the summary error line - save current error and stop
                        if current_error:
                            test_errors.append(current_error)
                            current_error = None
                        break

                # Save last error if exists
                if current_error:
                    test_errors.append(current_error)

            cli_report = {
                "available": True,
                "returncode": result.returncode,
                "json_output": json_output,
                "stderr": result.stderr,
                "stdout": result.stdout,
                "full_output": full_output,  # Combined output for Test Summary parsing
                "test_errors": test_errors,  # Parsed test file errors
                "passed": result.returncode == 0,
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.info(
                f"Kyverno CLI completed with return code: {result.returncode}"
            )
            if result.stderr:
                self.logger.info(
                    f"Kyverno CLI stderr contains: {len(result.stderr)} characters"
                )
                # Log Test Summary if found
                if "Test Summary:" in result.stderr:
                    summary_lines = [
                        line
                        for line in result.stderr.split("\n")
                        if "Test Summary:" in line
                    ]
                    for line in summary_lines:
                        self.logger.info(f"Found Test Summary: {line.strip()}")

                # Log test errors if found
                if "Test errors:" in result.stdout:
                    self.logger.info(f"Found test errors in stdout")
                    self.logger.info(f"Test errors found: {len(test_errors)}")
                    for error in test_errors:
                        self.logger.info(f"Test error: {error}")
                else:
                    self.logger.info("No 'Test errors:' found in stdout")

            return cli_report

        except subprocess.TimeoutExpired:
            self.logger.error("Kyverno CLI test timed out")
            return {
                "available": True,
                "returncode": -1,
                "stdout": "",
                "stderr": "Kyverno CLI test timed out after 5 minutes",
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error running Kyverno CLI: {e}")
            return {
                "available": True,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Kyverno CLI error: {str(e)}",
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_yaml_report(
        self, validation_results: List[ValidationResult], output_dir: str
    ) -> str:
        """Generate YAML validation report in the exact format specified."""
        report_file = os.path.join(output_dir, "kyverno-validation-report.yaml")

        # Extract test statistics and failures from Kyverno CLI output
        total_tests = 0
        failed_tests = 0
        failures = []
        failed_policies = []
        test_file_errors = []

        # Look for CLI report data in validation results
        # We only need to process the JSON once since it's global for all policies
        kyverno_json = None
        for result in validation_results:
            if result.test_results and "kyverno_json" in result.test_results:
                kyverno_json = result.test_results["kyverno_json"]
                break

        # Extract test file errors
        for result in validation_results:
            if result.test_results and "test_errors" in result.test_results:
                test_file_errors.extend(result.test_results["test_errors"])
                break

        if kyverno_json:
            if isinstance(kyverno_json, list):
                # Each item in the list is a test failure
                for failure in kyverno_json:
                    if isinstance(failure, dict):
                        # Extract failure details in exact format
                        failure_entry = {
                            "ID": failure.get("ID", len(failures) + 1),
                            "POLICY": failure.get("POLICY", ""),
                            "REASON": failure.get("REASON", ""),
                            "RESOURCE": failure.get("RESOURCE", ""),
                            "RESULT": failure.get("RESULT", "Fail"),
                            "RULE": failure.get("RULE", ""),
                        }
                        failures.append(failure_entry)

                        # Track failed policies
                        policy_name = failure.get("POLICY", "")
                        if policy_name and policy_name not in failed_policies:
                            failed_policies.append(policy_name)
            elif isinstance(kyverno_json, dict):
                # Handle case where JSON is a dict (might contain parse errors or other info)
                self.logger.info(
                    f"Kyverno JSON is a dict with keys: {list(kyverno_json.keys())}"
                )

                # Check if it's a parse error case
                if "parse_error" in kyverno_json:
                    self.logger.warning(
                        f"JSON parse error: {kyverno_json['parse_error']}"
                    )
                    # Try to extract from raw_output if available
                    if "raw_output" in kyverno_json:
                        raw_output = kyverno_json["raw_output"]
                        self.logger.info(
                            f"Trying to parse raw output: {raw_output[:200]}..."
                        )
                        try:
                            parsed_json = json.loads(raw_output)
                            if isinstance(parsed_json, list):
                                kyverno_json = parsed_json
                                # Recursively process the list
                                for failure in kyverno_json:
                                    if isinstance(failure, dict):
                                        failure_entry = {
                                            "ID": failure.get("ID", len(failures) + 1),
                                            "POLICY": failure.get("POLICY", ""),
                                            "REASON": failure.get("REASON", ""),
                                            "RESOURCE": failure.get("RESOURCE", ""),
                                            "RESULT": failure.get("RESULT", "Fail"),
                                            "RULE": failure.get("RULE", ""),
                                        }
                                        failures.append(failure_entry)

                                        policy_name = failure.get("POLICY", "")
                                        if (
                                            policy_name
                                            and policy_name not in failed_policies
                                        ):
                                            failed_policies.append(policy_name)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Could not parse raw output: {e}")

                # Check if it's a single failure object (treat as list of one)
                elif "POLICY" in kyverno_json:
                    failure_entry = {
                        "ID": kyverno_json.get("ID", 1),
                        "POLICY": kyverno_json.get("POLICY", ""),
                        "REASON": kyverno_json.get("REASON", ""),
                        "RESOURCE": kyverno_json.get("RESOURCE", ""),
                        "RESULT": kyverno_json.get("RESULT", "Fail"),
                        "RULE": kyverno_json.get("RULE", ""),
                    }
                    failures.append(failure_entry)

                    policy_name = kyverno_json.get("POLICY", "")
                    if policy_name and policy_name not in failed_policies:
                        failed_policies.append(policy_name)
            else:
                self.logger.warning(
                    f"Kyverno JSON is unexpected type: {type(kyverno_json)}"
                )
        else:
            self.logger.warning("No Kyverno JSON found in validation results")

        # Extract total test count from CLI output (look for "Test Summary")
        for result in validation_results:
            if result.test_results:
                # Check CLI stderr first
                cli_output = result.test_results.get("cli_stderr", "")

                # Also check full output if stderr doesn't have Test Summary
                if not cli_output or "Test Summary:" not in cli_output:
                    cli_output = result.test_results.get("cli_full_output", "")

                if cli_output and "Test Summary:" in cli_output:
                    import re

                    # Look for pattern like "Test Summary: 1 out of 229 tests failed"
                    match = re.search(
                        r"Test Summary:\s*(\d+)\s+out\s+of\s+(\d+)\s+tests?\s+failed",
                        cli_output,
                    )
                    if match:
                        failed_tests = int(match.group(1))
                        total_tests = int(match.group(2))
                        self.logger.info(
                            f"Extracted from Test Summary: {failed_tests} failed out of {total_tests} total tests"
                        )
                        break

                    # Also look for pattern like "Test Summary: 229 tests passed"
                    match = re.search(
                        r"Test Summary:\s*(\d+)\s+tests?\s+passed", cli_output
                    )
                    if match and total_tests == 0:
                        total_tests = int(match.group(1))
                        failed_tests = 0
                        self.logger.info(
                            f"Extracted from Test Summary: {total_tests} tests passed, 0 failed"
                        )
                        break

                    # Look for any other Test Summary patterns
                    match = re.search(r"Test Summary:.*?(\d+).*?(\d+)", cli_output)
                    if match and total_tests == 0:
                        # Try to determine which number is which based on context
                        num1, num2 = int(match.group(1)), int(match.group(2))
                        if "failed" in cli_output.lower():
                            failed_tests = min(num1, num2)
                            total_tests = max(num1, num2)
                        else:
                            total_tests = max(num1, num2)
                            failed_tests = min(num1, num2)
                        self.logger.info(
                            f"Extracted from Test Summary (generic): {failed_tests} failed out of {total_tests} total tests"
                        )
                        break

        # If we couldn't extract from stderr, use the failure count and estimate
        if total_tests == 0:
            failed_tests = len(failures)
            # If there are test file errors but no test results, it means tests couldn't run
            if test_file_errors and failed_tests == 0:
                # Count policies with test file errors as failed
                failed_tests = len(test_file_errors)
                total_tests = len(
                    validation_results
                )  # Assume each policy should have tests
            else:
                # Estimate total tests - this is a fallback
                total_tests = max(failed_tests, len(validation_results))

        # Calculate success rate
        success_rate = 0.0
        if total_tests > 0:
            success_rate = ((total_tests - failed_tests) / total_tests) * 100

        # Create the exact report format you specified
        report = {
            "validation_report": {
                "total_tests": total_tests,
                "failed_tests": failed_tests,
                "failure": failures,
                "failed_policies": failed_policies,
                "success_rate": round(success_rate, 1),
            }
        }

        # Add test file errors if any exist
        if test_file_errors:
            report["validation_report"]["test_file_errors"] = test_file_errors

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                yaml.dump(report, f, default_flow_style=False, sort_keys=False)

            self.logger.info(f"Validation report generated: {report_file}")
            self.logger.info(
                f"Report summary: {total_tests} total tests, {failed_tests} failed, {success_rate:.1f}% success rate"
            )
            return report_file

        except Exception as e:
            self.logger.error(f"Error generating validation report: {e}")
            raise ValidationError(f"Failed to generate validation report: {e}")

    def _fix_test_failures(
        self,
        result: ValidationResult,
        policy: RecommendedPolicy,
        policy_dir: str,
        cli_report: Dict[str, Any],
    ) -> ValidationResult:
        """Fix test failures (when tests run but fail validation) using AI."""
        if not self.bedrock_client or not result.errors:
            return result

        self.logger.info(f"Fixing test failures for {result.policy_name}")

        try:
            # Check if this policy has actual test failures in the CLI report
            policy_failures = []
            if cli_report.get("json_output") and isinstance(
                cli_report["json_output"], list
            ):
                for failure in cli_report["json_output"]:
                    if (
                        isinstance(failure, dict)
                        and failure.get("POLICY") == result.policy_name
                    ):
                        policy_failures.append(failure)

            if not policy_failures:
                # No specific failures found in JSON, but we have errors - try to fix anyway
                self.logger.info(
                    f"No specific failures found for {result.policy_name}, attempting general fix"
                )

            # Read current test and policy files
            test_file_path = os.path.join(policy_dir, "kyverno-test.yaml")
            policy_file_path = os.path.join(policy_dir, f"{result.policy_name}.yaml")
            resource_file_path = os.path.join(policy_dir, "resource.yaml")

            if not os.path.exists(test_file_path):
                self.logger.warning(f"Test file not found: {test_file_path}")
                return result

            if not os.path.exists(policy_file_path):
                self.logger.warning(f"Policy file not found: {policy_file_path}")
                return result

            # Read current files
            with open(test_file_path, "r", encoding="utf-8") as f:
                current_test = f.read()

            with open(policy_file_path, "r", encoding="utf-8") as f:
                policy_content = f.read()

            resource_content = ""
            if os.path.exists(resource_file_path):
                with open(resource_file_path, "r", encoding="utf-8") as f:
                    resource_content = f.read()

            # Create backup
            backup_path = test_file_path + ".backup"
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(current_test)

            # Fix the test failures using AI
            fixed_content = self._fix_failing_tests_with_ai(
                test_file_path,
                result.errors,
                policy_failures,
                policy_content,
                current_test,
                resource_content,
            )

            if fixed_content and fixed_content != current_test:
                # Validate the fixed content is valid YAML
                try:
                    import yaml

                    yaml.safe_load(fixed_content)

                    # Write the fixed content
                    with open(test_file_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)

                    result.fixed_content = "AI fixes applied to failing test cases"
                    result.warnings.append(
                        f"Fixed test failures: {len(policy_failures)} specific failures addressed"
                    )
                    self.logger.info(
                        f"Successfully fixed test failures for {result.policy_name}"
                    )

                    # Remove backup since fix was successful
                    if os.path.exists(backup_path):
                        os.remove(backup_path)

                except yaml.YAMLError as e:
                    self.logger.warning(f"AI-generated fix has invalid YAML: {e}")
                    # Restore from backup
                    if os.path.exists(backup_path):
                        with open(backup_path, "r", encoding="utf-8") as f:
                            backup_content = f.read()
                        with open(test_file_path, "w", encoding="utf-8") as f:
                            f.write(backup_content)
                        os.remove(backup_path)
                    result.warnings.append(
                        f"Test failure fix failed: Invalid YAML generated"
                    )
            else:
                # Remove backup since no changes were made
                if os.path.exists(backup_path):
                    os.remove(backup_path)

        except Exception as e:
            self.logger.error(
                f"Error fixing test failures for {result.policy_name}: {e}"
            )
            result.warnings.append(f"Test failure fix failed: {e}")
            # Restore from backup if it exists
            backup_path = os.path.join(policy_dir, "kyverno-test.yaml.backup")
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        backup_content = f.read()
                    with open(
                        os.path.join(policy_dir, "kyverno-test.yaml"),
                        "w",
                        encoding="utf-8",
                    ) as f:
                        f.write(backup_content)
                    os.remove(backup_path)
                except Exception as restore_error:
                    self.logger.error(f"Failed to restore backup: {restore_error}")

        return result

    def _fix_failing_tests_with_ai(
        self,
        test_file_path: str,
        errors: List[str],
        policy_failures: List[Dict[str, Any]],
        policy_content: str,
        current_test: str,
        resource_content: str,
    ) -> Optional[str]:
        """Use AI to fix failing test cases (not parsing errors, but actual test failures)."""
        if not self.bedrock_client:
            return None

        try:
            # Format failure information for the AI
            failure_details = []
            for failure in policy_failures:
                failure_info = f"- Policy: {failure.get('POLICY', 'unknown')}"
                failure_info += f", Rule: {failure.get('RULE', 'unknown')}"
                failure_info += f", Resource: {failure.get('RESOURCE', 'unknown')}"
                failure_info += f", Reason: {failure.get('REASON', 'unknown')}"
                failure_details.append(failure_info)

            error_summary = "\n".join(errors) if errors else "Test validation failed"
            failures_summary = (
                "\n".join(failure_details)
                if failure_details
                else "No specific failure details available"
            )

            prompt = f"""
You are a Kyverno testing expert. Fix the failing test cases based on the validation failures.

POLICY CONTENT:
```yaml
{policy_content}
```

CURRENT TEST FILE:
```yaml
{current_test}
```

CURRENT RESOURCE FILE:
```yaml
{resource_content}
```

VALIDATION ERRORS:
{error_summary}

SPECIFIC TEST FAILURES:
{failures_summary}

INSTRUCTIONS:
1. Analyze why the tests are failing based on the error information
2. Fix the test expectations to match what the policy actually validates
3. Ensure test resource names match between test file and resource file
4. Fix any field name issues (e.g., 'resource' vs 'resources')
5. Ensure the test results (pass/fail) match the actual policy behavior
6. Keep the same test structure but fix the failing assertions
7. For CEL policies, ensure proper namespace context
8. Return only the corrected YAML test content

CORRECTED TEST FILE:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=4000, temperature=0.1
            )

            if response and response.strip():
                # Clean up the response (remove markdown code blocks if present)
                cleaned_response = response.strip()
                if cleaned_response.startswith("```yaml"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]

                return cleaned_response.strip()

        except Exception as e:
            self.logger.error(f"Error generating AI fix for failing tests: {e}")
            return None

        return None

    def _analyze_validation_errors(
        self, errors: List[str], policy_content: str
    ) -> Dict[str, Any]:
        """Analyze validation errors to understand what needs fixing."""
        analysis = {
            "error_types": [],
            "missing_files": [],
            "test_failures": [],
            "resource_issues": [],
            "policy_structure": {},
        }

        for error in errors:
            error_lower = error.lower()

            if "no such file" in error_lower or "not found" in error_lower:
                analysis["missing_files"].append(error)
            elif "fail" in error_lower and (
                "want pass" in error_lower or "got fail" in error_lower
            ):
                analysis["test_failures"].append(error)
            elif "resource" in error_lower:
                analysis["resource_issues"].append(error)
            else:
                analysis["error_types"].append(error)

        # Analyze policy structure
        try:
            policy_data = yaml.safe_load(policy_content)
            analysis["policy_structure"] = {
                "kind": policy_data.get("kind"),
                "name": policy_data.get("metadata", {}).get("name"),
                "rules_count": len(policy_data.get("spec", {}).get("rules", [])),
                "has_cel": self._has_cel_expressions(policy_data),
            }
        except Exception as e:
            analysis["policy_structure"]["parse_error"] = str(e)

        return analysis

    def _fix_test_file_errors(
        self,
        result: ValidationResult,
        policy: RecommendedPolicy,
        policy_dir: str,
        test_errors: List[Dict[str, str]],
    ) -> ValidationResult:
        """Fix test file parsing errors using AI."""
        if not self.bedrock_client or not test_errors:
            return result

        self.logger.info(f"Fixing test file errors for {result.policy_name}")

        try:
            # Find test file errors for this policy
            policy_test_errors = []
            test_file_path = os.path.join(policy_dir, "kyverno-test.yaml")

            for error in test_errors:
                error_path = error.get("path", "")
                # Check if this error is for the current policy's test file
                if policy_dir in error_path or test_file_path in error_path:
                    policy_test_errors.append(error)

            if not policy_test_errors:
                return result

            # Read the current test file
            if not os.path.exists(test_file_path):
                self.logger.warning(f"Test file not found: {test_file_path}")
                return result

            with open(test_file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Create backup
            backup_path = test_file_path + ".backup"
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(original_content)

            # Fix the test file using AI
            fixed_content = self._fix_malformed_test_file_with_ai(
                test_file_path,
                policy_test_errors,
                policy.customized_content,
                original_content,
            )

            if fixed_content and fixed_content != original_content:
                # Validate the fixed content is valid YAML
                try:
                    import yaml

                    yaml.safe_load(fixed_content)

                    # Write the fixed content
                    with open(test_file_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)

                    result.fixed_content = "AI fixes applied to malformed test file"
                    result.warnings.append(
                        f"Fixed test file parsing errors: {[e.get('error', '') for e in policy_test_errors]}"
                    )
                    self.logger.info(
                        f"Successfully fixed test file errors for {result.policy_name}"
                    )

                    # Remove backup since fix was successful
                    if os.path.exists(backup_path):
                        os.remove(backup_path)

                except yaml.YAMLError as e:
                    self.logger.warning(f"AI-generated fix has invalid YAML: {e}")
                    # Restore from backup
                    if os.path.exists(backup_path):
                        with open(backup_path, "r", encoding="utf-8") as f:
                            backup_content = f.read()
                        with open(test_file_path, "w", encoding="utf-8") as f:
                            f.write(backup_content)
                        os.remove(backup_path)
                    result.warnings.append(
                        f"Test file fix failed: Invalid YAML generated"
                    )
            else:
                # Remove backup since no changes were made
                if os.path.exists(backup_path):
                    os.remove(backup_path)

        except Exception as e:
            self.logger.error(
                f"Error fixing test file errors for {result.policy_name}: {e}"
            )
            result.warnings.append(f"Test file fix failed: {e}")
            # Restore from backup if it exists
            backup_path = os.path.join(policy_dir, "kyverno-test.yaml.backup")
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        backup_content = f.read()
                    with open(
                        os.path.join(policy_dir, "kyverno-test.yaml"),
                        "w",
                        encoding="utf-8",
                    ) as f:
                        f.write(backup_content)
                    os.remove(backup_path)
                except Exception as restore_error:
                    self.logger.error(f"Failed to restore backup: {restore_error}")

        return result

    def _fix_malformed_test_file_with_ai(
        self,
        test_file_path: str,
        test_errors: List[Dict[str, str]],
        policy_content: str,
        original_content: str,
    ) -> Optional[str]:
        """Use AI to fix malformed test files with parsing errors."""
        if not self.bedrock_client:
            return None

        try:
            error_descriptions = []
            for error in test_errors:
                error_msg = error.get("error", "")
                error_descriptions.append(f"- {error_msg}")

            prompt = f"""
You are a Kyverno testing expert. Fix the malformed test file that has parsing errors.

PARSING ERRORS:
{chr(10).join(error_descriptions)}

CURRENT TEST FILE CONTENT:
```yaml
{original_content}
```

POLICY CONTENT (for reference):
```yaml
{policy_content}
```

Common issues to fix:
1. Duplicate YAML keys (like duplicate 'rule' fields) - remove duplicates
2. Unknown fields (like 'resource' instead of 'name') - use correct field names
3. Invalid YAML structure - fix syntax errors

Please provide the corrected test file content that:
1. Fixes all parsing errors mentioned above
2. Maintains the same test logic and expectations
3. Uses valid Kyverno test file structure
4. Is syntactically correct YAML

Return ONLY the corrected YAML content, no explanations:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=2000, temperature=0.1
            )

            if response and response.strip():
                # Clean up the response (remove markdown code blocks if present)
                cleaned_response = response.strip()
                if cleaned_response.startswith("```yaml"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]

                return cleaned_response.strip()

        except Exception as e:
            self.logger.error(f"Error generating AI fix for malformed test file: {e}")
            return None

        return None

    def _fix_test_case_with_ai(
        self, test_file: str, errors: List[str], policy_content: str
    ) -> Optional[str]:
        """Use AI to fix failing test cases."""
        if not self.bedrock_client:
            return None

        try:
            # Read current test content
            with open(test_file, "r", encoding="utf-8") as f:
                current_test = f.read()

            prompt = f"""
You are a Kyverno testing expert. Fix the failing test case based on the validation errors.

POLICY CONTENT:
{policy_content}

CURRENT TEST CASE:
{current_test}

VALIDATION ERRORS:
{chr(10).join(errors)}

INSTRUCTIONS:
1. Analyze the validation errors and identify what's wrong with the test case
2. Fix the test case to make it pass validation
3. Ensure test resources match the expected results
4. Keep the test structure but fix the failing assertions
5. For CEL policies, ensure proper namespace context
6. Return only the fixed YAML test content

FIXED TEST CASE:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=3000, temperature=0.2
            )

            # Clean up response
            response = response.strip()
            if response.startswith("```yaml"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Validate the fixed test
            try:
                yaml.safe_load(response)
                return response
            except yaml.YAMLError as e:
                self.logger.warning(f"AI-generated fix has invalid YAML: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Error fixing test case with AI: {e}")
            return None

    def _generate_test_resources_with_ai(
        self, policy: RecommendedPolicy, error_analysis: Dict[str, Any]
    ) -> str:
        """Generate test resources using AI based on error analysis."""
        if not self.bedrock_client:
            return self._generate_basic_test_resources(policy)

        try:
            prompt = f"""
You are a Kyverno testing expert. Generate test resources for the following policy.

POLICY CONTENT:
{policy.customized_content}

ERROR ANALYSIS:
{json.dumps(error_analysis, indent=2)}

INSTRUCTIONS:
1. Create test resources that will work with the policy
2. Include both resources that should pass and fail the policy
3. Consider the error analysis to avoid common issues
4. For CEL policies, ensure proper namespace context
5. Generate realistic Kubernetes resources
6. Return only YAML resource content with multiple documents separated by ---

TEST RESOURCES:
"""

            response = self.bedrock_client.send_request(
                prompt, max_tokens=2500, temperature=0.2
            )

            # Clean up response
            response = response.strip()
            if response.startswith("```yaml"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Validate the generated resources
            try:
                list(yaml.safe_load_all(response))
                return response
            except yaml.YAMLError as e:
                self.logger.warning(f"AI-generated resources have invalid YAML: {e}")
                return self._generate_basic_test_resources(policy)

        except Exception as e:
            self.logger.error(f"Error generating test resources with AI: {e}")
            return self._generate_basic_test_resources(policy)

    def _check_kyverno_cli(self) -> bool:
        """Check if Kyverno CLI is available."""
        try:
            result = subprocess.run(
                ["kyverno", "version"], capture_output=True, text=True, timeout=10
            )
            available = result.returncode == 0
            if available:
                self.logger.info("Kyverno CLI is available")
            else:
                self.logger.warning(
                    "Kyverno CLI not available - validation will be limited"
                )
            return available
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            self.logger.warning(
                "Kyverno CLI not available - validation will be limited"
            )
            return False

    def check_kyverno_available(self) -> bool:
        """Public method to check if Kyverno CLI is available (for test compatibility)."""
        return self.kyverno_cli_available

    def validate_policies(self, policy_dir: str) -> Dict[str, Any]:
        """Validate policies in a directory (for test compatibility)."""
        # Check if Kyverno CLI is available first
        if not self.check_kyverno_available():
            raise ValidationError("Kyverno CLI is not available")

        try:
            cli_report = self._execute_kyverno_cli_test(policy_dir)

            # Parse the CLI report into the expected format
            report = {
                "total_tests": 0,
                "failed_tests": 0,
                "success_rate": 100.0,
                "failure": [],
                "failed_policies": [],
            }

            # Check if test file errors exist
            if cli_report.get("test_errors"):
                report["test_file_errors"] = cli_report["test_errors"]
            else:
                # Parse test file errors from stderr if not already parsed
                stderr = cli_report.get("stderr", "")
                if stderr:
                    test_errors = self._parse_test_file_errors(stderr)
                    if test_errors:
                        report["test_file_errors"] = test_errors

            # Extract information from CLI report
            if cli_report.get("json_output"):
                json_output = cli_report["json_output"]
                if isinstance(json_output, list):
                    report["failed_tests"] = len(json_output)
                    report["failure"] = json_output
                    report["failed_policies"] = list(
                        set(
                            failure.get("POLICY", "")
                            for failure in json_output
                            if isinstance(failure, dict) and failure.get("POLICY")
                        )
                    )
            else:
                # Parse failures from stdout if no JSON output
                stdout = cli_report.get("stdout", "")
                if stdout:
                    failures = []
                    lines = stdout.split("\n")
                    for line in lines:
                        line = line.strip()
                        if "FAIL:" in line:
                            parts = line.split(" -> ")
                            if len(parts) >= 2:
                                policy_info = parts[0].replace("FAIL:", "").strip()
                                reason = parts[1].strip()

                                # Parse policy/rule/resource from policy_info
                                policy_parts = policy_info.split("/")
                                policy_name = (
                                    policy_parts[0]
                                    if len(policy_parts) > 0
                                    else "unknown"
                                )

                                failure = {
                                    "policy": policy_name,
                                    "rule": (
                                        policy_parts[1]
                                        if len(policy_parts) > 1
                                        else "unknown"
                                    ),
                                    "resource": (
                                        policy_parts[2]
                                        if len(policy_parts) > 2
                                        else "unknown"
                                    ),
                                    "reason": reason,
                                }
                                failures.append(failure)

                    if failures:
                        report["failure"] = failures
                        report["failed_policies"] = list(
                            set(failure.get("policy", "") for failure in failures)
                        )

            # Try to extract total tests from stderr or stdout
            stderr = cli_report.get("stderr", "")
            stdout = cli_report.get("stdout", "")
            combined_output = stdout + "\n" + stderr

            if "Test Summary:" in combined_output:
                import re

                match = re.search(
                    r"(\d+)\s+out\s+of\s+(\d+)\s+tests?\s+failed", combined_output
                )
                if match:
                    report["failed_tests"] = int(match.group(1))
                    report["total_tests"] = int(match.group(2))
                else:
                    match = re.search(r"(\d+)\s+tests?\s+passed", combined_output)
                    if match:
                        report["total_tests"] = int(match.group(1))
                        report["failed_tests"] = 0
            else:
                # If no Test Summary, try to count PASS/FAIL lines in stdout
                if stdout:
                    import re

                    pass_matches = re.findall(r"PASS:", stdout)
                    fail_matches = re.findall(r"FAIL:", stdout)
                    if pass_matches or fail_matches:
                        report["total_tests"] = len(pass_matches) + len(fail_matches)
                        report["failed_tests"] = len(fail_matches)

            # Calculate success rate
            if report["total_tests"] > 0:
                report["success_rate"] = (
                    (report["total_tests"] - report["failed_tests"])
                    / report["total_tests"]
                ) * 100

            return report

        except Exception as e:
            self.logger.error(f"Error validating policies: {e}")
            return {
                "total_tests": 0,
                "failed_tests": 1,
                "success_rate": 0.0,
                "failure": [{"error": str(e)}],
                "failed_policies": [],
            }

    def _find_test_files(self, directory: str) -> List[str]:
        """Find test files in a directory (for test compatibility)."""
        test_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith((".yaml", ".yml")) and (
                    "test" in file.lower() or file == "kyverno-test.yaml"
                ):
                    test_files.append(os.path.join(root, file))
        return test_files

    def _parse_kyverno_output(self, output: str, stderr: str) -> Dict[str, Any]:
        """Parse Kyverno CLI output (for test compatibility)."""
        report = {
            "total_tests": 0,
            "failed_tests": 0,
            "success_rate": 100.0,
            "failure": [],
            "failed_policies": [],
        }

        # Combine output and stderr for parsing
        combined_output = output + "\n" + stderr

        # Look for test summary in combined output
        if "Test Summary:" in combined_output:
            import re

            match = re.search(
                r"(\d+)\s+out\s+of\s+(\d+)\s+tests?\s+failed", combined_output
            )
            if match:
                report["failed_tests"] = int(match.group(1))
                report["total_tests"] = int(match.group(2))
            else:
                match = re.search(r"(\d+)\s+tests?\s+passed", combined_output)
                if match:
                    report["total_tests"] = int(match.group(1))
                    report["failed_tests"] = 0

        # Parse test results from output - look for PASS/FAIL patterns
        lines = output.split("\n")
        pass_count = 0
        fail_count = 0

        for line in lines:
            line = line.strip()
            if "PASS:" in line:
                pass_count += 1
            elif "FAIL:" in line:
                fail_count += 1
                parts = line.split(" -> ")
                if len(parts) >= 2:
                    policy_info = parts[0].replace("FAIL:", "").strip()
                    reason = parts[1].strip()

                    # Parse policy/rule/resource from policy_info
                    policy_parts = policy_info.split("/")
                    policy_name = (
                        policy_parts[0] if len(policy_parts) > 0 else "unknown"
                    )

                    failure = {
                        "policy": policy_name,
                        "rule": policy_parts[1] if len(policy_parts) > 1 else "unknown",
                        "resource": (
                            policy_parts[2] if len(policy_parts) > 2 else "unknown"
                        ),
                        "reason": reason,
                    }
                    report["failure"].append(failure)

                    # Track failed policies
                    if policy_name not in report["failed_policies"]:
                        report["failed_policies"].append(policy_name)

        # If we found PASS/FAIL patterns, use those counts
        if pass_count > 0 or fail_count > 0:
            report["total_tests"] = pass_count + fail_count
            report["failed_tests"] = fail_count

        # Calculate success rate
        if report["total_tests"] > 0:
            report["success_rate"] = round(
                (
                    (report["total_tests"] - report["failed_tests"])
                    / report["total_tests"]
                )
                * 100,
                1,
            )

        return report

    def _parse_test_file_errors(self, stderr: str) -> List[Dict[str, str]]:
        """Parse test file errors from stderr (for test compatibility)."""
        errors = []
        lines = stderr.split("\n")

        for line in lines:
            line = line.strip()
            if "Error:" in line and (
                "failed to load" in line or "failed to parse" in line
            ):
                # Extract file path and error message
                if "failed to load test file" in line:
                    # Pattern: "Error: failed to load test file /path/to/test.yaml: duplicate key 'rule'"
                    parts = line.split("failed to load test file")
                    if len(parts) > 1:
                        path_and_error = parts[1].strip()
                        if ":" in path_and_error:
                            path, error = path_and_error.split(":", 1)
                            errors.append(
                                {"path": path.strip(), "error": error.strip()}
                            )
                elif "failed to parse resource file" in line:
                    # Pattern: "Error: failed to parse resource file /path/to/resource.yaml: invalid YAML"
                    parts = line.split("failed to parse resource file")
                    if len(parts) > 1:
                        path_and_error = parts[1].strip()
                        if ":" in path_and_error:
                            path, error = path_and_error.split(":", 1)
                            errors.append(
                                {"path": path.strip(), "error": error.strip()}
                            )

        return errors

    def save_validation_report(self, report: Dict[str, Any], report_file: str) -> None:
        """Save validation report to file (for test compatibility)."""
        try:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, "w", encoding="utf-8") as f:
                yaml.dump({"validation_report": report}, f, default_flow_style=False)
            self.logger.info(f"Validation report saved: {report_file}")
        except Exception as e:
            self.logger.error(f"Error saving validation report: {e}")
            raise ValidationError(f"Failed to save validation report: {e}")

    def _find_policy_directory(
        self, policy_name: str, output_dir: str
    ) -> Optional[str]:
        """Find the directory containing the policy files."""
        for root, dirs, files in os.walk(output_dir):
            if policy_name in dirs:
                return os.path.join(root, policy_name)

            # Also check if any directory contains the policy file
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if os.path.exists(os.path.join(dir_path, f"{policy_name}.yaml")):
                    return dir_path

        return None

    def _extract_policy_result_from_cli(
        self, policy_name: str, cli_report: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract policy-specific results from CLI JSON output."""
        if not cli_report.get("available"):
            return None

        json_output = cli_report.get("json_output")
        stderr = cli_report.get("stderr", "")

        # Parse JSON output from Kyverno CLI
        errors = []
        warnings = []
        passed = True

        try:
            if not json_output:
                # No JSON output with --fail-only means all tests passed
                return {
                    "passed": True,
                    "errors": [],
                    "warnings": [],
                    "kyverno_json": None,
                }

            # Handle case where JSON parsing failed
            if isinstance(json_output, dict) and "parse_error" in json_output:
                return {
                    "passed": False,
                    "errors": [
                        f"Failed to parse Kyverno output: {json_output['parse_error']}"
                    ],
                    "warnings": [],
                    "kyverno_json": json_output,
                }

            # Handle case where no failures were found
            if isinstance(json_output, dict) and json_output.get("all_tests_passed"):
                return {
                    "passed": True,
                    "errors": [],
                    "warnings": [],
                    "kyverno_json": json_output,
                }

            # JSON output is a list of test failure objects
            if isinstance(json_output, (list, dict)):
                test_results = (
                    json_output if isinstance(json_output, list) else [json_output]
                )

                for test_result in test_results:
                    if not isinstance(test_result, dict):
                        continue

                    # Check if this test result is for our policy (exact format from Kyverno)
                    test_policy = test_result.get("POLICY", "")
                    if test_policy == policy_name:
                        # Found a failure for this policy
                        passed = False

                        # Extract error details from the JSON structure (exact field names from Kyverno)
                        reason = test_result.get("REASON", "Unknown failure")
                        resource = test_result.get("RESOURCE", "Unknown resource")
                        rule = test_result.get("RULE", "Unknown rule")
                        result_status = test_result.get("RESULT", "Fail")
                        test_id = test_result.get("ID", "")

                        error_msg = f"Policy failure: {reason}"
                        if resource != "Unknown resource":
                            error_msg += f" - Failed resource: {resource}"
                        if rule != "Unknown rule":
                            error_msg += f" - Rule: {rule}"

                        errors.append(error_msg)

            # If no specific failures found for this policy in JSON, it likely passed
            if not errors and cli_report.get("returncode") != 0:
                # Check stderr for any policy-specific errors
                if stderr and policy_name in stderr:
                    errors.append(f"CLI error: {stderr}")
                    passed = False

        except Exception as e:
            self.logger.warning(f"Error parsing CLI output for {policy_name}: {e}")
            passed = False
            errors.append(f"Error parsing results: {e}")

        # Check stderr for additional errors
        if stderr and policy_name in stderr:
            stderr_lines = stderr.split("\n")
            for line in stderr_lines:
                if policy_name in line and (
                    "error" in line.lower() or "fail" in line.lower()
                ):
                    errors.append(line.strip())
                    passed = False

        # If no specific results found, assume passed (no news is good news with --fail-only)
        if not errors and not warnings and cli_report.get("passed", True):
            passed = True

        # Create test summary
        test_summary = {
            "total_tests": 1,  # Assume one test per policy
            "passed_tests": 1 if passed else 0,
            "failed_tests": 0 if passed else 1,
        }

        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "test_summary": test_summary,
            "cli_stderr": stderr if stderr else None,
            "kyverno_json": json_output,
        }

    def _parse_yaml_test_results(
        self, yaml_data: Dict[str, Any], policy_name: str
    ) -> Dict[str, Any]:
        """Parse YAML test results from Kyverno CLI output."""
        results = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "test_count": 0,
            "failure_count": 0,
        }

        try:
            # Look for test results in the YAML structure
            if "results" in yaml_data:
                test_results = yaml_data["results"]
                if isinstance(test_results, list):
                    for result in test_results:
                        if (
                            isinstance(result, dict)
                            and result.get("policy") == policy_name
                        ):
                            results["test_count"] += 1
                            if result.get("result") == "fail":
                                results["failure_count"] += 1
                                results["passed"] = False
                                error_msg = f"Test failed for rule '{result.get('rule', 'unknown')}'"
                                if "resource" in result:
                                    error_msg += f" on resource '{result['resource']}'"
                                if "reason" in result:
                                    error_msg += f": {result['reason']}"
                                results["errors"].append(error_msg)

            # Look for summary information
            if "summary" in yaml_data:
                summary = yaml_data["summary"]
                if isinstance(summary, dict):
                    if summary.get("failed", 0) > 0:
                        results["passed"] = False

        except Exception as e:
            self.logger.warning(f"Error parsing YAML test results: {e}")

        return results

    def _generate_test_resources(self, policy: RecommendedPolicy) -> str:
        """Generate basic test resources for a policy."""
        return self._generate_basic_test_resources(policy)

    def _generate_basic_test_resources(self, policy: RecommendedPolicy) -> str:
        """Generate basic test resources without AI."""
        try:
            policy_data = yaml.safe_load(policy.customized_content)
            policy_name = policy.original_policy.name

            # Special cases for known policy types
            if "service-mesh" in policy_name.lower():
                return self._generate_service_mesh_resources()
            elif "disallow-default-namespace" in policy_name.lower():
                return self._generate_namespace_resources()
            elif "require-pod-resources" in policy_name.lower():
                return self._generate_resource_limit_resources()

            # Generic resource generation
            return self._generate_generic_resources()

        except Exception as e:
            self.logger.error(f"Error generating basic test resources: {e}")
            return self._generate_generic_resources()

    def _has_cel_expressions(self, policy_data: Dict[str, Any]) -> bool:
        """Check if policy uses CEL expressions."""
        rules = policy_data.get("spec", {}).get("rules", [])
        for rule in rules:
            validate = rule.get("validate", {})
            if "cel" in validate:
                return True
        return False

    def _generate_fix_recommendations(
        self, validation_results: List[ValidationResult]
    ) -> List[str]:
        """Generate recommendations for fixing validation issues."""
        recommendations = []

        failed_results = [r for r in validation_results if not r.passed]

        if not failed_results:
            recommendations.append("All policies passed validation!")
            return recommendations

        # Analyze common failure patterns
        common_errors = {}
        for result in failed_results:
            for error in result.errors:
                error_type = self._categorize_error(error)
                common_errors[error_type] = common_errors.get(error_type, 0) + 1

        # Generate recommendations based on common errors
        for error_type, count in common_errors.items():
            if error_type == "missing_files":
                recommendations.append(
                    f"Generate missing test files for {count} policies"
                )
            elif error_type == "test_failures":
                recommendations.append(
                    f"Review and fix test expectations for {count} policies"
                )
            elif error_type == "resource_issues":
                recommendations.append(f"Update test resources for {count} policies")
            elif error_type == "namespace_issues":
                recommendations.append(f"Fix namespace context for {count} policies")

        if self.enable_ai_fixes:
            fixed_count = sum(1 for r in validation_results if r.fixed_content)
            if fixed_count > 0:
                recommendations.append(
                    f"AI fixes were applied to {fixed_count} policies"
                )
        else:
            recommendations.append(
                "Enable --fix flag to apply AI-powered fixes automatically"
            )

        return recommendations

    def _extract_cli_summary(self, cli_output: str) -> Dict[str, Any]:
        """Extract clean summary from Kyverno CLI output."""
        if not cli_output:
            return {}

        summary = {
            "total_tests": 0,
            "failed_tests": 0,
            "passed_tests": 0,
            "policies_with_failures": [],
            "output_format": "unknown",
        }

        lines = cli_output.split("\n")

        # Look for the test summary line
        for line in lines:
            if "Test Summary:" in line:
                # Parse line like "Test Summary: 1 out of 229 tests failed"
                import re

                match = re.search(r"(\d+)\s+out\s+of\s+(\d+)\s+tests?\s+failed", line)
                if match:
                    summary["failed_tests"] = int(match.group(1))
                    summary["total_tests"] = int(match.group(2))
                    summary["passed_tests"] = (
                        summary["total_tests"] - summary["failed_tests"]
                    )
                    summary["output_format"] = "text_summary"
                break

        # Extract failed policies
        current_policy = None
        for line in lines:
            if line.startswith("POLICY:"):
                current_policy = line.replace("POLICY:", "").strip()
                if current_policy not in summary["policies_with_failures"]:
                    summary["policies_with_failures"].append(current_policy)

        # Try to parse as YAML if no text summary found
        if summary["output_format"] == "unknown":
            try:
                yaml_data = yaml.safe_load(cli_output)
                if yaml_data and isinstance(yaml_data, dict):
                    summary["output_format"] = "yaml"
                    if "summary" in yaml_data:
                        yaml_summary = yaml_data["summary"]
                        summary["total_tests"] = yaml_summary.get("total", 0)
                        summary["failed_tests"] = yaml_summary.get("failed", 0)
                        summary["passed_tests"] = yaml_summary.get("passed", 0)
            except yaml.YAMLError:
                pass

        return summary

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _clean_result_for_report(self, result: ValidationResult) -> Dict[str, Any]:
        """Clean validation result for YAML report (exclude verbose CLI output)."""
        return {
            "policy_name": result.policy_name,
            "passed": result.passed,
            "errors": result.errors,
            "warnings": result.warnings,
            "has_fixes": bool(result.fixed_content),
            "generated_tests": result.generated_tests,
            "validation_timestamp": (
                result.validation_report.get("timestamp")
                if result.validation_report
                else None
            ),
        }

    def _categorize_error(self, error: str) -> str:
        """Categorize error type for recommendations."""
        error_lower = error.lower()

        if "no such file" in error_lower or "not found" in error_lower:
            return "missing_files"
        elif "namespace" in error_lower and (
            "default" in error_lower or "context" in error_lower
        ):
            return "namespace_issues"
        elif "fail" in error_lower and (
            "want pass" in error_lower or "got fail" in error_lower
        ):
            return "test_failures"
        elif "resource" in error_lower:
            return "resource_issues"
        else:
            return "other"

    # Abstract method implementations required by PolicyValidatorInterface

    def validate_policy(
        self, policy_content: str, test_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate a single policy using Kyverno CLI (legacy interface method)."""
        try:
            # Create a temporary policy for validation
            policy_name = "temp-policy"
            try:
                policy_data = yaml.safe_load(policy_content)
                policy_name = policy_data.get("metadata", {}).get("name", "temp-policy")
            except yaml.YAMLError:
                # If YAML parsing fails, use default name
                policy_name = "temp-policy"

            # Create minimal policy entry
            catalog_entry = PolicyCatalogEntry(
                name=policy_name,
                category="Temp",
                description="Temporary policy for validation",
                relative_path=f"{policy_name}.yaml",
                test_directory=None,
                source_repo="temp",
                tags=[],
            )

            recommended_policy = RecommendedPolicy(
                original_policy=catalog_entry,
                customized_content=policy_content,
                test_content=test_content,
                category="Temp",
                customizations_applied=[],
                validation_status="pending",
            )

            # Use the new validation method
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create temporary directory structure
                policy_dir = os.path.join(temp_dir, policy_name)
                os.makedirs(policy_dir, exist_ok=True)

                # Write policy file
                policy_file = os.path.join(policy_dir, f"{policy_name}.yaml")
                with open(policy_file, "w") as f:
                    f.write(policy_content)

                # Write test file if provided
                if test_content:
                    test_file = os.path.join(policy_dir, "kyverno-test.yaml")
                    with open(test_file, "w") as f:
                        f.write(test_content)

                # Run validation
                result = self._validate_single_policy(recommended_policy, temp_dir, {})

                return {
                    "passed": result.passed,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "validation_type": "kyverno_validator",
                    "test_results": result.test_results,
                }

        except Exception as e:
            self.logger.error(f"Error in legacy validate_policy method: {e}")
            return {
                "passed": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "validation_type": "error",
            }

    def fix_policy_issues(
        self, policy_content: str, validation_errors: List[str]
    ) -> str:
        """Attempt to fix common policy issues (legacy interface method)."""
        # IMPORTANT: We should never modify policy content as per requirements
        # Policies should be copied as-is from the catalog
        self.logger.info(
            "Policy content will not be modified - copying as-is from catalog"
        )
        return policy_content

    def generate_test_case(self, policy_content: str) -> str:
        """Generate test case for policy if missing (legacy interface method)."""
        try:
            # Parse policy to understand its structure
            policy_data = yaml.safe_load(policy_content)

            if not policy_data or policy_data.get("kind") not in [
                "ClusterPolicy",
                "Policy",
            ]:
                raise ValidationError("Invalid policy format")

            policy_name = policy_data.get("metadata", {}).get("name", "unknown-policy")

            # Use dedicated test case generator if available
            if self.test_case_generator:
                return self.test_case_generator.generate_comprehensive_test_case(
                    policy_content, policy_name
                )

            # Fallback to template-based test generation
            return self._generate_template_test_case(policy_data, policy_name)

        except Exception as e:
            self.logger.error(f"Error generating test case: {e}")
            return self._generate_minimal_test_case(
                policy_name if "policy_name" in locals() else "unknown"
            )

    def _generate_template_test_case(
        self, policy_data: Dict[str, Any], policy_name: str
    ) -> str:
        """Generate template-based test case."""
        # Extract resource kinds from policy rules
        resource_kinds = set()
        rules = policy_data.get("spec", {}).get("rules", [])

        for rule in rules:
            match = rule.get("match", {})
            if "any" in match:
                for any_match in match["any"]:
                    resources = any_match.get("resources", {})
                    kinds = resources.get("kinds", [])
                    resource_kinds.update(kinds)
            elif "resources" in match:
                kinds = match["resources"].get("kinds", [])
                resource_kinds.update(kinds)

        # Default to Pod if no kinds found
        if not resource_kinds:
            resource_kinds = {"Pod"}

        # Generate basic test structure using new Kyverno test format
        test_case = {
            "apiVersion": "cli.kyverno.io/v1alpha1",
            "kind": "Test",
            "metadata": {"name": f"{policy_name}-test"},
            "policies": [f"{policy_name}.yaml"],
            "resources": ["resource.yaml"],
            "results": [],
        }

        # Add expected results for each resource kind
        for kind in resource_kinds:
            test_case["results"].append(
                {
                    "policy": policy_name,
                    "rule": (
                        rules[0].get("name", "default-rule")
                        if rules
                        else "default-rule"
                    ),
                    "resource": f"test-{kind.lower()}",
                    "kind": kind,
                    "result": "pass",
                }
            )

        return yaml.dump(test_case, default_flow_style=False)

    def _generate_minimal_test_case(self, policy_name: str) -> str:
        """Generate minimal test case as fallback."""
        test_case = {
            "apiVersion": "cli.kyverno.io/v1alpha1",
            "kind": "Test",
            "metadata": {"name": f"{policy_name}-test"},
            "policies": [f"{policy_name}.yaml"],
            "resources": ["resource.yaml"],
            "results": [
                {
                    "policy": policy_name,
                    "rule": "default-rule",
                    "resource": "test-resource",
                    "kind": "Pod",
                    "result": "pass",
                }
            ],
        }

        return yaml.dump(test_case, default_flow_style=False)

    def _generate_service_mesh_resources(self) -> str:
        """Generate test resources for service mesh policies."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: good-pod
  namespace: default
  labels:
    app: test-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
  containers:
  - name: app-container
    image: nginx:latest
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
---
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: app-container
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
"""

    def _generate_namespace_resources(self) -> str:
        """Generate test resources for namespace policies."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: badpod01
  namespace: default
  labels:
    app: myapp
spec:
  containers:
  - name: nginx
    image: nginx
---
apiVersion: v1
kind: Pod
metadata:
  name: goodpod01
  namespace: foo
  labels:
    app: myapp
spec:
  containers:
  - name: nginx
    image: nginx
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: baddeployment01
  labels:
    app: busybox
spec:
  replicas: 1
  selector:
    matchLabels:
      app: busybox
  template:
    metadata:
      labels:
        app: busybox
    spec:
      containers:
      - image: busybox:1.28
        name: busybox
        command: ["sleep", "9999"]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gooddeployment01
  labels:
    app: busybox
  namespace: foo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: busybox
  template:
    metadata:
      labels:
        app: busybox
    spec:
      containers:
      - image: busybox:1.28
        name: busybox
        command: ["sleep", "9999"]
"""

    def _generate_resource_limit_resources(self) -> str:
        """Generate test resources for resource limit policies."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: good-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: app-container
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
---
apiVersion: v1
kind: Pod
metadata:
  name: bad-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: app-container
    image: nginx:latest
    # Missing resource limits - should fail policy
"""

    def _generate_generic_resources(self) -> str:
        """Generate generic test resources."""
        return """apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  namespace: default
  labels:
    app: test-app
spec:
  containers:
  - name: test-container
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deployment
  namespace: default
  labels:
    app: test-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: test-container
        image: nginx:latest
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "128Mi"
            cpu: "500m"
"""
