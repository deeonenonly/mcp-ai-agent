
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "sample_project"
APP_FILE = PROJECT_DIR / "app.py"
REPORT_DIR = BASE_DIR / "reports"


def extract_verified_facts(tool_output):
    """Extract summary and individual test results from the MCP server."""

    passed_match = re.search(r"Passed:\s*(\d+)", tool_output)
    failed_match = re.search(r"Failed:\s*(\d+)", tool_output)
    exit_code_match = re.search(
        r"Pytest exit code:\s*(\d+)", tool_output
    )

    passed = int(passed_match.group(1)) if passed_match else None
    failed = int(failed_match.group(1)) if failed_match else None
    exit_code = (
        int(exit_code_match.group(1))
        if exit_code_match
        else None
    )

    # Extract the JSON array of individual test outcomes from server.py.
    individual_tests = []
    marker = "INDIVIDUAL TEST RESULTS JSON:\n"
    start = tool_output.find(marker)

    if start != -1:
        start += len(marker)
        end = tool_output.find("\n\nRAW PYTEST OUTPUT:", start)

        if end != -1:
            try:
                parsed_tests = json.loads(tool_output[start:end].strip())

                if isinstance(parsed_tests, list):
                    individual_tests = parsed_tests

            except json.JSONDecodeError:
                individual_tests = []

    # Determine the failing test and expected/actual values.
    failing_test_match = re.search(
        r"FAILED\s+\S+::(\w+)", tool_output
    )

    expected_match = re.search(
        r"assert apply_discount\(200, 10\) == (\d+)",
        tool_output,
    )

    actual_match = re.search(
        r"assert (\d+) == (\d+)", tool_output
    )

    if exit_code == 0:
        failed = 0
        failing_test = "No failing test"
        expected = None
        actual = None
    else:
        failing_test = (
            failing_test_match.group(1)
            if failing_test_match
            else "Not identified"
        )

        expected = (
            int(expected_match.group(1))
            if expected_match
            else None
        )

        actual = (
            int(actual_match.group(1))
            if actual_match
            else None
        )

    return {
        "passed": passed,
        "failed": failed,
        "failing_test": failing_test,
        "expected": expected,
        "actual": actual,
        "pytest_exit_code": exit_code,
        "individual_tests": individual_tests,
    }


def save_report(facts, diagnosis, tool_output):
    """Save verified results and AI diagnosis in a timestamped JSON report."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    exit_code = facts["pytest_exit_code"]

    if exit_code == 0:
        status = "PASSED"
    elif exit_code is not None:
        status = "FAILED"
    else:
        status = "UNKNOWN"

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "project": "MCP-Enabled AI Testing Agent",
        "test_results": {
            "passed": facts["passed"],
            "failed": facts["failed"],
            "failing_test": facts["failing_test"],
            "expected_value": facts["expected"],
            "actual_value": facts["actual"],
            "pytest_exit_code": exit_code,
            "execution_status": status,
            "individual_tests": facts.get("individual_tests", []),
        },
        "ai_diagnosis": diagnosis,
        "verification": {
            "correction_applied": False,
            "correction_retested": False,
            "note": (
                "The client does not automatically modify application "
                "files. A proposed correction must be applied and "
                "tested separately."
            ),
        },
        "raw_pytest_output": tool_output,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_path = REPORT_DIR / f"test_report_{timestamp}.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    return report_path


def get_ai_diagnosis(user_request, application_code, facts, tool_output):
    """Ask Ollama to diagnose a verified test failure."""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a software testing and debugging assistant. "
                "Use the supplied application source and pytest evidence "
                "to explain the root cause of the failure. Suggest a "
                "minimal correction and explain it. Do not modify files, "
                "claim that a fix was applied, or invent test results. "
                "The supplied test facts and output are authoritative."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User request:\n{user_request}\n\n"
                f"Actual application source:\n{application_code}\n\n"
                f"Verified test facts:\n{json.dumps(facts, indent=2)}\n\n"
                f"Pytest output:\n{tool_output}\n\n"
                "Explain the actual failure and suggest a correction. "
                "Do not claim that the correction has been applied or "
                "tested."
            ),
        },
    ]

    response = ollama.chat(
        model="llama3.2:3b",
        messages=messages,
    )

    return response.message.content


async def main():
    user_request = input("You: ").strip()

    if not user_request:
        print("Please enter a request.")
        return

    testing_keywords = (
        "test",
        "pytest",
        "failure",
        "failing",
        "debug",
        "analyse",
        "analyze",
        "diagnos",
    )

    if not any(word in user_request.lower() for word in testing_keywords):
        print("Please ask me to run or analyse the tests.")
        return

    server_script = BASE_DIR / "server.py"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = await session.list_tools()
            available_tools = {
                tool.name for tool in mcp_tools.tools
            }

            if "run_tests" not in available_tools:
                print("Error: MCP server does not expose run_tests.")
                return

            result = await session.call_tool(
                "run_tests",
                arguments={},
            )

            if result.isError:
                print("MCP test execution failed.")
                return

            tool_output = "\n".join(
                item.text
                for item in result.content
                if hasattr(item, "text")
            )

            facts = extract_verified_facts(tool_output)

            print("\n--- Actual MCP Test Results ---")
            print(tool_output)

            print("\n--- Verified Test Facts ---")
            print(f"Passed tests: {facts['passed']}")
            print(f"Failed tests: {facts['failed']}")
            print(f"Failing test: {facts['failing_test']}")
            print(f"Expected value: {facts['expected']}")
            print(f"Actual value: {facts['actual']}")

            print("\n--- Individual Test Results ---")

            if facts["individual_tests"]:
                for test in facts["individual_tests"]:
                    print(
                        f"{test.get('test_id', test.get('test_name', 'Unknown'))}"
                        f" | {test.get('status', 'UNKNOWN')}"
                    )
            else:
                print(
                    "Individual test outcomes were unavailable. "
                    "Check the MCP server output."
                )

            if facts["pytest_exit_code"] is None:
                diagnosis = (
                    "Test status is unknown because the server did not "
                    "provide a valid pytest exit code. Check the raw output."
                )

            elif facts["pytest_exit_code"] == 0:
                diagnosis = (
                    "All tests passed. No failure diagnosis was needed."
                )

                print("\n--- Test Analysis ---")
                print(diagnosis)

            else:
                print("\n--- AI Failure Diagnosis ---")

                try:
                    application_code = APP_FILE.read_text(
                        encoding="utf-8"
                    )

                    diagnosis = get_ai_diagnosis(
                        user_request,
                        application_code,
                        facts,
                        tool_output,
                    )

                    print(diagnosis)

                except Exception as error:
                    diagnosis = (
                        f"AI diagnosis unavailable: {error}. "
                        "Refer to the verified test facts and raw output."
                    )

                    print(diagnosis)

            try:
                report_path = save_report(
                    facts,
                    diagnosis,
                    tool_output,
                )

                print("\n--- Report Generated ---")
                print(f"Report saved to: {report_path}")
                print("Format: JSON")

            except OSError as error:
                print(f"\nUnable to save report: {error}")

            print("\n--- Verification Status ---")

            if facts["pytest_exit_code"] == 0:
                print("All tests passed in the original test run.")
            elif facts["pytest_exit_code"] is not None:
                print("The test run reported a non-zero exit code.")
            else:
                print("The final test status could not be verified.")

            print("No application files were modified automatically.")


if __name__ == "__main__":
    asyncio.run(main())
