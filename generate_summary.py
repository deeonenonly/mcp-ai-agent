import json
from datetime import datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"
COMPARISON_PATH = REPORT_DIR / "comparison_summary.json"
OUTPUT_PATH = REPORT_DIR / "latest_test_summary.md"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def timestamp_value(value, fallback_path):
    try:
        if value:
            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).timestamp()
    except (ValueError, TypeError, OverflowError):
        pass

    return fallback_path.stat().st_mtime


def markdown_cell(value):
    if value is None or value == "":
        return "-"
    return str(value).replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def main():
    candidates = []

    for path in REPORT_DIR.glob("test_report_*.json"):
        try:
            data = load_json(path)
            generated_at = data.get("generated_at") or data.get("timestamp")
            sort_key = timestamp_value(generated_at, path)
            candidates.append((sort_key, path, data))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Skipping unreadable report {path.name}: {error}")

    if not candidates:
        print("ERROR: No readable test reports found in reports/.")
        sys.exit(1)

    latest_time, latest_path, report = max(
        candidates, key=lambda item: item[0]
    )

    results = report.get("test_results") or {}
    passed = int(results.get("passed") or 0)
    failed = int(results.get("failed") or 0)
    exit_code = results.get("pytest_exit_code")
    recorded_status = str(results.get("execution_status") or "").upper()

    if failed > 0 or (exit_code is not None and exit_code != 0):
        status = "FAILED"
    elif recorded_status in ("PASSED", "FAILED"):
        status = recorded_status
    elif exit_code == 0:
        status = "PASSED"
    else:
        status = "UNKNOWN"

    generated_at = (
        report.get("generated_at")
        or report.get("timestamp")
        or "Not recorded"
    )
    project = report.get("project") or "Not specified"
    individual_tests = results.get("individual_tests") or []
    diagnosis = report.get("ai_diagnosis") or "No AI diagnosis was recorded."

    lines = [
        "# Intelligent Test Execution Report",
        "",
        f"_Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}_",
        "",
        "## Latest Test Run",
        "",
        f"- **Project:** {project}",
        f"- **Run timestamp:** {generated_at}",
        f"- **Overall status:** **{status}**",
        f"- **Tests passed:** {passed}",
        f"- **Tests failed:** {failed}",
        f"- **Pytest exit code:** {exit_code if exit_code is not None else 'Not recorded'}",
        f"- **Source report:** `{latest_path.name}`",
        "",
    ]

    failing_test = results.get("failing_test")
    if failed > 0:
        lines.extend(["## Failure Details", ""])
        if failing_test and failing_test != "No failing test":
            lines.append(f"- **Failing test:** `{failing_test}`")
        lines.append(
            f"- **Expected value:** {results.get('expected_value', 'Not recorded')}"
        )
        lines.append(
            f"- **Actual value:** {results.get('actual_value', 'Not recorded')}"
        )
        lines.append("")

    lines.extend(["## Individual Test Results", ""])

    if individual_tests:
        lines.extend([
            "| Test | Status |",
            "|---|---|",
        ])
        for test in individual_tests:
            name = markdown_cell(
                test.get("test_name") or test.get("test_id") or "Unknown test"
            )
            test_status = markdown_cell(test.get("status", "UNKNOWN"))
            lines.append(f"| {name} | {test_status} |")
    else:
        lines.append("No individual test results were included in the report.")

    lines.extend([
        "",
        "## AI Failure Diagnosis",
        "",
        str(diagnosis).strip(),
        "",
        "The AI diagnosis is advisory. Any suggested code correction must be "
        "reviewed, applied separately, and verified by rerunning the tests.",
        "",
        "## Recovery History",
        "",
    ])

    if COMPARISON_PATH.exists():
        try:
            comparison = load_json(COMPARISON_PATH)
            comparison_time = (
                comparison.get("generated_at") or "Not recorded"
            )
            lines.append(f"- **Comparison generated:** {comparison_time}")
            lines.append(
                f"- **Reports analyzed:** {comparison.get('reports_analyzed', 'Not recorded')}"
            )

            if timestamp_value(comparison.get("generated_at"), COMPARISON_PATH) < latest_time:
                lines.extend([
                    "",
                    "> **Note:** The comparison summary may be out of date. "
                    "Run `python compare_reports.py` and regenerate this report.",
                ])

            suite = comparison.get("suite_recovery") or {}
            if suite.get("recovery_verified"):
                lines.extend([
                    "- **Suite recovery verified:** Yes",
                    f"- **Failure run:** `{suite.get('failure_report', 'Not recorded')}`",
                    f"- **Recovery run:** `{suite.get('recovery_report', 'Not recorded')}`",
                ])
            else:
                lines.append(
                    "- **Suite recovery verified:** No recorded FAILED → PASSED transition"
                )
                if suite.get("reason"):
                    lines.append(f"- **Details:** {suite['reason']}")

            recoveries = comparison.get("individual_test_regressions") or []
            verified_recoveries = [
                item for item in recoveries if item.get("recovery_verified")
            ]

            if verified_recoveries:
                lines.extend([
                    "",
                    "### Individual-Test Recoveries",
                    "",
                    "| Test | Failure run | Recovery run |",
                    "|---|---|---|",
                ])
                for item in verified_recoveries:
                    name = markdown_cell(item.get("test_name", "Unknown test"))
                    failure = markdown_cell(item.get("failure_report"))
                    recovery = markdown_cell(item.get("recovery_report"))
                    lines.append(f"| {name} | {failure} | {recovery} |")
            else:
                lines.extend([
                    "",
                    "No verified individual-test recoveries were recorded.",
                ])

        except (OSError, json.JSONDecodeError) as error:
            lines.append(f"Unable to read the comparison summary: {error}")
    else:
        lines.extend([
            "Comparison summary not found.",
            "Run `python compare_reports.py` to generate recovery history.",
        ])

    lines.extend([
        "",
        "## Interpretation",
        "",
    ])

    if status == "PASSED":
        lines.append("The latest recorded test run passed.")
    elif status == "FAILED":
        lines.append(
            "The latest recorded test run failed. Review the failure details "
            "and AI diagnosis, correct the issue manually, and rerun the tests."
        )
    else:
        lines.append(
            "The latest run's status could not be established confidently. "
            "Inspect the source JSON report and pytest output."
        )

    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Markdown report generated successfully.")
    print(f"Latest test run: {status} ({passed} passed, {failed} failed)")
    print(f"Report saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
