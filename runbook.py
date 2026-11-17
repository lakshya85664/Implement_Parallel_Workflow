
"""
Topic 4 - Task 5: Operator Runbook and Evidence Report

Generates:
- Operator runbook.
- Evidence inventory and validation report.
- Final operator summary.

The report reads existing Task 1-4 evidence files.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
TRACE_DIR = BASE_DIR / "traces"
REPORT_DIR = BASE_DIR / "reports"

RUNBOOK_FILE = REPORT_DIR / "OPERATOR_RUNBOOK.md"
EVIDENCE_FILE = REPORT_DIR / "evidence_report.json"
FINAL_REPORT_FILE = OUTPUT_DIR / "task5_operator_report.json"


EXPECTED_EVIDENCE = [
    OUTPUT_DIR / "task1_workflow_contract.json",
    OUTPUT_DIR / "task2_parallel_execution.json",
    OUTPUT_DIR / "task3_failure_recovery.json",
    OUTPUT_DIR / "task4_integration_observability.json",
    OUTPUT_DIR / "task4_measurement_report.json",
    TRACE_DIR / "task3_retry_trace.json",
    TRACE_DIR / "task4_observability_trace.json",
]


def inspect_evidence() -> dict[str, Any]:
    """Check expected evidence files and validate JSON content."""

    inventory = []

    for path in EXPECTED_EVIDENCE:
        exists = path.is_file()
        valid_json = False
        error = None

        try:
            display_path = str(path.relative_to(BASE_DIR))
        except ValueError:
            # Supports pytest temporary files outside the project directory.
            display_path = str(path)

        if exists:
            try:
                with path.open("r", encoding="utf-8") as file:
                    json.load(file)

                valid_json = True

            except (json.JSONDecodeError, OSError) as exc:
                error = type(exc).__name__

        inventory.append({
            "file": display_path,
            "exists": exists,
            "valid_json": valid_json,
            "error": error,
        })

    found_count = sum(item["exists"] for item in inventory)
    valid_count = sum(item["valid_json"] for item in inventory)

    return {
        "expected_count": len(EXPECTED_EVIDENCE),
        "found_count": found_count,
        "valid_json_count": valid_count,
        "complete": (
            found_count == len(EXPECTED_EVIDENCE)
            and valid_count == len(EXPECTED_EVIDENCE)
        ),
        "files": inventory,
    }


def load_json(path: Path) -> dict[str, Any]:
    """Load an existing JSON evidence file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_runbook() -> str:
    """Build the operator documentation."""

    return """# Topic 4 — Parallel Workflow Operator Runbook

## 1. Purpose

This runbook explains how to execute, monitor, troubleshoot, and
recover the parallel order-validation workflow.

The workflow validates three independent conditions:

1. Credit eligibility.
2. Inventory availability.
3. Delivery address validity.

The order approval task is executed only after all three checks
have returned valid results.

## 2. Architecture and execution

The workflow uses the following pattern:

- Fan-out: submit the three independent checks.
- Worker pool: execute checks concurrently using ThreadPoolExecutor.
- Synchronization: wait for the check results.
- Fan-in: collect and validate all results.
- Approval: approve only if all prerequisites succeed.

## 3. Environment setup

Open Windows CMD and navigate to:

`E:\\Tayana_Projects\\Workflow_Orchestration\\Implement_Parallel_Workflow`

Activate the virtual environment:

```cmd
.venv\\Scripts\\activate
```

Install pytest if required:

```cmd
pip install pytest
```

## 4. Execution commands

Run the workflow contract:

```cmd
python parallel_workflow.py
```

Run the parallel execution:

```cmd
python parallel_executor.py
```

Run the failure and recovery demonstration:

```cmd
python reliability.py
```

Run the integration and observability demonstration:

```cmd
python adapters.py
```

Generate the operator documentation:

```cmd
python runbook.py
```

Run the complete test suite:

```cmd
python -m pytest -v
```

## 5. Expected successful execution

The three independent checks should report success.

Expected output characteristics:

- Credit check: eligible.
- Inventory check: sufficient stock.
- Address check: valid.
- Successful checks: 3.
- Failed checks: 0.
- Approval: true.
- Final workflow state: completed.

The Task 2 evidence is stored in:

`outputs/task2_parallel_execution.json`

## 6. Failure handling

### Transient dependency failure

Action:

1. Inspect the retry trace.
2. Confirm the error is classified as transient.
3. Allow the configured bounded retry policy.
4. Check whether the operation recovered.
5. Escalate to operator review if retries are exhausted.

Evidence:

`outputs/task3_failure_recovery.json`

### Permanent failure

Action:

1. Do not retry a permanent business rejection.
2. Inspect the error reason.
3. Check the business input and service response.
4. Route the order to operator review.

### Malformed response

Action:

1. Quarantine the invalid response.
2. Inspect the expected response contract.
3. Verify the service adapter.
4. Do not continue approval with invalid data.

### Timeout

Action:

1. Identify the task that exceeded its deadline.
2. Inspect dependency health.
3. Verify client-level timeout configuration.
4. Retry only when safe and appropriate.
5. Escalate if the dependency remains unavailable.

## 7. Idempotency and replay safety

The Idempotency mechanism uses an idempotency key to prevent
a repeated operation from producing a duplicate side effect.

Operator procedure:

1. Locate the original business key.
2. Inspect the original operation result.
3. Reuse the same idempotency key for a replay.
4. Confirm that the stored result is returned.
5. Confirm that the side-effect count has not increased.

The duplicate workflow trigger guard also prevents a repeated
business key from creating a second run within its in-memory store.

Evidence:

`outputs/task3_failure_recovery.json`

## 8. Integration boundary and observability

The integration boundary uses injectable fake adapters for:

- Credit service.
- Inventory service.
- Address service.

Each service call produces a structured trace with:

- Run ID.
- Task ID.
- Service name.
- Outcome.
- Timestamp.
- Duration.
- Redacted response details.

Sensitive values such as passwords, API keys, and tokens are
redacted before trace output.

Trace evidence:

- `traces/task3_retry_trace.json`
- `traces/task4_observability_trace.json`

Measurement evidence:

- `outputs/task4_measurement_report.json`

## 9. Operator action by workflow state

| State | Meaning | Operator action |
|---|---|---|
| created | Run has been initialized | Verify input and start conditions |
| running | Checks are executing | Monitor task results and traces |
| waiting | Workflow is paused | Inspect the outstanding dependency |
| completed | All required checks succeeded | Confirm the approval result |
| needs_review | A failure requires attention | Inspect errors and choose a safe recovery action |

## 10. Measurements

The Task 4 measurement report records:

- Workflow starts.
- Workflow completions.
- Workflow failures.
- Task successes and failures.
- Total service calls.
- Total latency.
- Average latency.
- Maximum latency.

These values are generated from the synthetic adapter demonstration.

## 11. Known limitations

- All service adapters use synthetic business data.
- No production provider or external API is contacted.
- The idempotency and trigger stores are in-memory.
- In-memory state does not provide distributed deduplication.
- Python cannot forcibly terminate an already-running worker thread.
- Production integrations must enforce client-level timeouts.
- Production deployment requires persistent state, secure secret
  management, distributed locking, and operational alerting.

## 12. Recovery checklist

- [ ] Identify the workflow run.
- [ ] Identify the failed task.
- [ ] Inspect the structured trace.
- [ ] Classify the failure.
- [ ] Check whether retry is permitted.
- [ ] Verify idempotency before replay.
- [ ] Confirm all fan-in prerequisites.
- [ ] Record the recovery outcome.
"""


def build_final_report(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Summarize execution, recovery, and measurements."""

    task2 = load_json(
        OUTPUT_DIR / "task2_parallel_execution.json"
    )

    task3 = load_json(
        OUTPUT_DIR / "task3_failure_recovery.json"
    )

    task4 = load_json(
        OUTPUT_DIR / "task4_integration_observability.json"
    )

    metrics = load_json(
        OUTPUT_DIR / "task4_measurement_report.json"
    )

    return {
        "task": "Task 5 - Operator Runbook and Evidence Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_complete": evidence["complete"],
        "evidence_summary": {
            "expected": evidence["expected_count"],
            "found": evidence["found_count"],
            "valid_json": evidence["valid_json_count"],
        },
        "happy_path": {
            "workflow_state": task2["workflow_state"],
            "approval": task2["approval"]["approved"],
            "successful_checks": task2["parallel_checks"]["success_count"],
            "failed_checks": task2["parallel_checks"]["failure_count"],
            "elapsed_ms": task2["parallel_checks"]["elapsed_ms"],
        },
        "failure_recovery": {
            "transient_status": task3["transient_failure"]["status"],
            "transient_attempts": task3["transient_failure"]["attempts"],
            "permanent_status": task3["permanent_failure"]["status"],
            "malformed_status": task3["malformed_response"]["status"],
            "timeout_status": task3["timeout"]["status"],
            "replay_prevented_duplicate": (
                task3["idempotency"]["side_effect_count"] == 1
            ),
            "duplicate_trigger_blocked": (
                task3["duplicate_trigger"]["second"]["duplicate"]
            ),
        },
        "integration": {
            "workflow_success": task4["workflow_success"],
            "trace_count": task4["trace_count"],
            "metrics": metrics,
        },
        "operator_actions": {
            "completed": "Verify approval and archive the run evidence.",
            "needs_review": "Inspect the failure and authorize safe recovery.",
            "timeout": "Inspect dependency health and enforce client timeout.",
            "replay": "Reuse the original idempotency key.",
            "malformed_response": "Quarantine and inspect the response contract.",
        },
        "limitations": [
            "Synthetic adapters only; no production API calls.",
            "Idempotency and duplicate trigger stores are in-memory.",
            "Running Python threads cannot be forcibly terminated.",
            "Production deployment requires durable state and distributed controls.",
        ],
    }


def generate_reports() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    evidence = inspect_evidence()

    runbook = build_runbook()

    RUNBOOK_FILE.write_text(
        runbook,
        encoding="utf-8",
    )

    EVIDENCE_FILE.write_text(
        json.dumps(evidence, indent=4),
        encoding="utf-8",
    )

    final_report = build_final_report(evidence)

    FINAL_REPORT_FILE.write_text(
        json.dumps(final_report, indent=4),
        encoding="utf-8",
    )

    print("=" * 65)
    print("TASK 5 - OPERATOR RUNBOOK AND EVIDENCE REPORT")
    print("=" * 65)

    print(f"Expected evidence files: {evidence['expected_count']}")
    print(f"Found evidence files: {evidence['found_count']}")
    print(f"Valid JSON files: {evidence['valid_json_count']}")
    print(f"Evidence complete: {evidence['complete']}")

    print(f"\nCreated: {RUNBOOK_FILE}")
    print(f"Created: {EVIDENCE_FILE}")
    print(f"Created: {FINAL_REPORT_FILE}")

    return final_report


if __name__ == "__main__":
    generate_reports()
