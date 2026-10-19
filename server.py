
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Software Testing Server")

PROJECT_DIR = Path(__file__).resolve().parent / "sample_project"
TESTS_DIR = PROJECT_DIR / "tests"


def read_individual_test_results(xml_path: Path) -> list[dict]:
    """Read individual test names and outcomes from pytest's JUnit XML."""
    root = ET.parse(xml_path).getroot()
    test_results = []

    for case in root.iter("testcase"):
        test_name = case.attrib.get("name", "unknown_test")
        class_name = case.attrib.get("classname", "")

        test_id = (
            f"{class_name}::{test_name}"
            if class_name
            else test_name
        )

        if case.find("failure") is not None or case.find("error") is not None:
            status = "FAILED"
        elif case.find("skipped") is not None:
            status = "SKIPPED"
        else:
            status = "PASSED"

        test_results.append(
            {
                "test_id": test_id,
                "test_name": test_name,
                "status": status,
            }
        )

    return test_results


@mcp.tool()
def run_tests() -> str:
    """Run pytest and return summary and individual test results."""

    junit_path = None

    try:
        # Create a temporary location for pytest's structured results.
        with tempfile.NamedTemporaryFile(
            prefix="mcp_pytest_",
            suffix=".xml",
            delete=False,
        ) as temporary_file:
            junit_path = Path(temporary_file.name)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(TESTS_DIR),
                "-q",
                "--tb=short",
                f"--junitxml={junit_path}",
            ],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=20,
        )

        output = result.stdout + "\n" + result.stderr

        failed_match = re.search(r"(\d+)\s+failed", output)
        passed_match = re.search(r"(\d+)\s+passed", output)

        failed = int(failed_match.group(1)) if failed_match else 0
        passed = int(passed_match.group(1)) if passed_match else 0

        # Read per-test results from the XML file.
        individual_tests = read_individual_test_results(junit_path)

        individual_lines = [
            f'{test["test_id"]} | {test["status"]} '
            f'| test_name={test["test_name"]}'
            for test in individual_tests
        ]

        individual_output = (
            "\n".join(individual_lines)
            if individual_lines
            else "No individual test results were available."
        )

        return (
            "AUTHORITATIVE TEST SUMMARY\n"
            f"Passed: {passed}\n"
            f"Failed: {failed}\n"
            f"Pytest exit code: {result.returncode}\n"
            f"{'All tests passed.' if result.returncode == 0 else 'Tests failed or pytest encountered an execution error.'}\n\n"
            "INDIVIDUAL TEST RESULTS:\n"
            f"{individual_output}\n\n"
            "INDIVIDUAL TEST RESULTS JSON:\n"
            f"{json.dumps(individual_tests)}\n\n"
            "RAW PYTEST OUTPUT:\n"
            f"{output.strip()}"
        )

    except subprocess.TimeoutExpired:
        return "Test execution timed out after 20 seconds."

    except Exception as error:
        return f"Unable to execute tests: {error}"

    finally:
        # Remove the temporary XML file after reading the results.
        if junit_path is not None:
            try:
                junit_path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    mcp.run(transport="stdio")
