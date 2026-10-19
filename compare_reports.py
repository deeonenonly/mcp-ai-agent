
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"
SUMMARY_FILE = REPORT_DIR / "comparison_summary.json"


def load_reports():
    """Load reports in chronological order, oldest first."""
    reports = []

    for path in REPORT_DIR.glob("test_report_*.json"):
        try:
            with path.open("r", encoding="utf-8") as file:
                report = json.load(file)

            report["_file"] = path.name
            reports.append(report)

        except (OSError, json.JSONDecodeError) as error:
            print(f"Skipping {path.name}: {error}")

    def sort_key(report):
        timestamp = report.get("timestamp") or report.get("generated_at")

        if timestamp:
            try:
                return datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, TypeError, OverflowError):
                pass

        # Timestamped report filenames sort chronologically.
        return report["_file"]

    return sorted(reports, key=sort_key)


def get_test_results(report):
    """Return individual test outcomes indexed by test name."""
    test_results = report.get("test_results", {})
    individual_tests = test_results.get("individual_tests", [])

    results = {}

    for test in individual_tests:
        name = test.get("test_name")

        if not name:
            test_id = test.get("test_id", "")
            name = test_id.rsplit("::", 1)[-1]

        status = str(test.get("status", "")).upper()

        if name and status in {"PASSED", "FAILED", "SKIPPED"}:
            results[name] = status

    return results


def get_suite_status(report):
    """Determine suite outcome from the saved report."""
    results = report.get("test_results", {})

    exit_code = results.get("pytest_exit_code")

    if exit_code is not None:
        return "PASSED" if exit_code == 0 else "FAILED"

    status = str(results.get("execution_status", "")).upper()

    if status in {"PASSED", "FAILED"}:
        return status

    passed = results.get("passed")
    failed = results.get("failed")

    if isinstance(passed, int) and isinstance(failed, int):
        if failed > 0:
            return "FAILED"
        if passed > 0:
            return "PASSED"

    return "UNKNOWN"


def verify_individual_regressions(reports):
    """
    Verify recovery only when the latest recorded test result is PASSED
    and a FAILED result occurred before it.
    """
    history = {}

    for report in reports:
        for test_name, status in get_test_results(report).items():
            history.setdefault(test_name, []).append(
                {
                    "status": status,
                    "report": report["_file"],
                }
            )

    regressions = []

    for test_name, entries in history.items():
        failures = [
            entry for entry in entries
            if entry["status"] == "FAILED"
        ]

        if not failures:
            continue

        latest_entry = entries[-1]

        # Recovery is valid only if the latest recorded result passed.
        if latest_entry["status"] == "PASSED":
            # Find the most recent failure before the latest passing result.
            previous_failures = [
                entry for entry in entries[:-1]
                if entry["status"] == "FAILED"
            ]

            if previous_failures:
                failure = previous_failures[-1]

                regressions.append(
                    {
                        "test_name": test_name,
                        "recovery_verified": True,
                        "failure_report": failure["report"],
                        "recovery_report": latest_entry["report"],
                        "failure_status": "FAILED",
                        "recovery_status": "PASSED",
                    }
                )
                continue

        regressions.append(
            {
                "test_name": test_name,
                "recovery_verified": False,
                "latest_failure_report": failures[-1]["report"],
                "latest_status": latest_entry["status"],
                "latest_report": latest_entry["report"],
                "reason": (
                    "The latest recorded result is not PASSED, "
                    "so recovery is not currently verified."
                    if latest_entry["status"] != "PASSED"
                    else "No earlier failure was found before the latest passing result."
                ),
            }
        )

    return regressions



def verify_suite_recovery(reports):
    """Find the most recent FAILED -> PASSED suite transition."""
    recovery = None

    for index in range(1, len(reports)):
        previous_report = reports[index - 1]
        current_report = reports[index]

        previous_status = get_suite_status(previous_report)
        current_status = get_suite_status(current_report)

        if previous_status == "FAILED" and current_status == "PASSED":
            recovery = {
                "recovery_verified": True,
                "failure_report": previous_report["_file"],
                "recovery_report": current_report["_file"],
            }

    if recovery:
        return recovery

    return {
        "recovery_verified": False,
        "reason": "No consecutive FAILED -> PASSED suite transition was found.",
    }



def main():
    reports = load_reports()

    if not reports:
        print("No test reports were found in the reports directory.")
        return

    print("\n========== TEST RUN HISTORY ==========")

    for report in reports:
        test_results = report.get("test_results", {})
        print(
            f'{report["_file"]} | '
            f'Suite: {get_suite_status(report)} | '
            f'Passed: {test_results.get("passed", "N/A")} | '
            f'Failed: {test_results.get("failed", "N/A")}'
        )

    suite_recovery = verify_suite_recovery(reports)
    individual_regressions = verify_individual_regressions(reports)

    print("\n========== SUITE RECOVERY ==========")

    if suite_recovery["recovery_verified"]:
        print("PASS: A passing suite run followed a failed suite run.")
        print(f'Failure report: {suite_recovery["failure_report"]}')
        print(f'Recovery report: {suite_recovery["recovery_report"]}')
    else:
        print("NOT VERIFIED: " + suite_recovery["reason"])

    print("\n========== INDIVIDUAL-TEST REGRESSION VERIFICATION ==========")

    if not individual_regressions:
        print(
            "NOT VERIFIED: No individual test failure was found "
            "in reports containing individual test outcomes."
        )

    for result in individual_regressions:
        print(f'\nTest: {result["test_name"]}')

        if result["recovery_verified"]:
            print("PASS: FAILED -> PASSED")
            print(f'Failure report: {result["failure_report"]}')
            print(f'Recovery report: {result["recovery_report"]}')
        else:
            print("NOT VERIFIED: No later passing result was found.")
            print(f'Reason: {result["reason"]}')

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "reports_analyzed": len(reports),
        "suite_recovery": suite_recovery,
        "individual_test_regressions": individual_regressions,
    }

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SUMMARY_FILE.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"\nComparison summary saved to: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
