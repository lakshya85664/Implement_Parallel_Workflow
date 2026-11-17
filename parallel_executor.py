
"""
Topic 4 - Task 2: Parallel Workflow Implementation

Implements:
- Fan-out of independent checks.
- ThreadPoolExecutor worker pool.
- Synchronization using concurrent.futures.wait.
- Fan-in validation before approval.
- Per-task timeout handling.
- Structured execution results and measurements.
"""

from __future__ import annotations

import json
import time

from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
    ALL_COMPLETED,
)
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from parallel_workflow import (
    TaskResult,
    TaskStatus,
    WorkflowInput,
    WorkflowRun,
    WorkflowState,
    build_topic_fixture,
    transition,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_FILE = OUTPUT_DIR / "task2_parallel_execution.json"

MAX_WORKERS = 3
TASK_TIMEOUT_SECONDS = 2.0


def check_credit(
    workflow_input: WorkflowInput,
) -> TaskResult:
    """Synthetic credit eligibility check."""

    time.sleep(0.15)

    approved = workflow_input.customer_id.startswith("CUSTOMER")

    return TaskResult(
        task_id="TASK-CREDIT",
        success=approved,
        status="succeeded" if approved else "failed",
        data={
            "customer_id": workflow_input.customer_id,
            "credit_eligible": approved,
        },
        error=None if approved else "Credit eligibility check failed",
    )


def check_inventory(
    workflow_input: WorkflowInput,
) -> TaskResult:
    """Synthetic inventory availability check."""

    time.sleep(0.15)

    available_quantity = 10
    available = available_quantity >= workflow_input.quantity

    return TaskResult(
        task_id="TASK-INVENTORY",
        success=available,
        status="succeeded" if available else "failed",
        data={
            "sku": workflow_input.sku,
            "requested_quantity": workflow_input.quantity,
            "available_quantity": available_quantity,
            "inventory_available": available,
        },
        error=None if available else "Insufficient inventory",
    )


def check_address(
    workflow_input: WorkflowInput,
) -> TaskResult:
    """Synthetic delivery address validation."""

    time.sleep(0.15)

    valid = bool(workflow_input.delivery_address.strip())

    return TaskResult(
        task_id="TASK-ADDRESS",
        success=valid,
        status="succeeded" if valid else "failed",
        data={
            "delivery_address": workflow_input.delivery_address,
            "address_valid": valid,
        },
        error=None if valid else "Invalid delivery address",
    )


CHECK_FUNCTIONS: dict[str, Callable[[WorkflowInput], TaskResult]] = {
    "TASK-CREDIT": check_credit,
    "TASK-INVENTORY": check_inventory,
    "TASK-ADDRESS": check_address,
}


def update_task(
    run: WorkflowRun,
    result: TaskResult,
) -> None:
    """Update the matching task with its execution result."""

    task = next(
        task for task in run.tasks
        if task.task_id == result.task_id
    )

    task.status = (
        TaskStatus.SUCCEEDED
        if result.success
        else TaskStatus.FAILED
    )

    task.result = result.data
    task.error = result.error
    task.attempts += 1


def execute_parallel_checks(
    run: WorkflowRun,
    workflow_input: WorkflowInput,
    *,
    max_workers: int = MAX_WORKERS,
    timeout_seconds: float = TASK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    Fan out independent checks and synchronize their results.

    Approval is not performed here. It is a separate fan-in operation.
    """

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    run.state = WorkflowState.RUNNING
    run.record(
        "parallel_checks.started",
        {
            "max_workers": max_workers,
            "timeout_seconds": timeout_seconds,
        },
    )

    started_at = time.perf_counter()

    futures = {}

    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="workflow-check",
    ) as executor:

        # FAN-OUT: submit all independent checks.
        for task_id, function in CHECK_FUNCTIONS.items():
            task = next(
                task for task in run.tasks
                if task.task_id == task_id
            )

            task.status = TaskStatus.RUNNING
            task.attempts += 1

            run.record(
                "task.submitted",
                {"task_id": task_id},
            )

            future = executor.submit(function, workflow_input)
            futures[future] = task_id

        # SYNCHRONIZATION: wait for completion or timeout.
        done, not_done = wait(
            futures,
            timeout=timeout_seconds,
            return_when=ALL_COMPLETED,
        )

        results: dict[str, TaskResult] = {}

        for future in done:
            task_id = futures[future]

            try:
                result = future.result()

            except Exception as exc:
                result = TaskResult(
                    task_id=task_id,
                    success=False,
                    status="failed",
                    error=f"Worker exception: {type(exc).__name__}",
                )

            # Avoid incrementing attempts twice: it was counted on submission.
            task = next(
                task for task in run.tasks
                if task.task_id == task_id
            )
            task.attempts -= 1

            update_task(run, result)
            results[task_id] = result

            run.record(
                "task.finished",
                {
                    "task_id": task_id,
                    "success": result.success,
                },
            )

            run.add_trace(
                task_id=task_id,
                operation="parallel_check",
                outcome="success" if result.success else "failure",
                details=result.data,
            )

        for future in not_done:
            task_id = futures[future]
            future.cancel()

            result = TaskResult(
                task_id=task_id,
                success=False,
                status="failed",
                error="Task execution timed out",
            )

            task = next(
                task for task in run.tasks
                if task.task_id == task_id
            )
            task.status = TaskStatus.FAILED
            task.error = result.error
            task.attempts += 1

            results[task_id] = result

            run.record(
                "task.timed_out",
                {"task_id": task_id},
            )

            run.add_trace(
                task_id=task_id,
                operation="parallel_check",
                outcome="timeout",
                details={"error": result.error},
            )

    elapsed_ms = (time.perf_counter() - started_at) * 1000

    success_count = sum(
        result.success for result in results.values()
    )

    failure_count = len(results) - success_count

    summary = {
        "results": {
            task_id: asdict(result)
            for task_id, result in results.items()
        },
        "success_count": success_count,
        "failure_count": failure_count,
        "timed_out_count": len(not_done),
        "elapsed_ms": round(elapsed_ms, 3),
        "max_workers": max_workers,
    }

    run.record(
        "parallel_checks.finished",
        {
            "success_count": success_count,
            "failure_count": failure_count,
            "elapsed_ms": round(elapsed_ms, 3),
        },
    )

    return summary


def approve_after_fan_in(
    run: WorkflowRun,
    results: dict[str, Any],
) -> dict[str, Any]:
    """
    FAN-IN: approve only if every independent check succeeded.
    """

    required_checks = {
        "TASK-CREDIT",
        "TASK-INVENTORY",
        "TASK-ADDRESS",
    }

    if set(results) != required_checks:
        raise ValueError(
            "Fan-in requires results from all three independent checks"
        )

    all_successful = all(
        result["success"]
        for result in results.values()
    )

    approval_task = next(
        task for task in run.tasks
        if task.task_id == "TASK-APPROVAL"
    )

    if all_successful:
        approval_task.status = TaskStatus.SUCCEEDED
        approval_task.result = {
            "approved": True,
            "order_id": run.input_data["order_id"],
        }

        run.record(
            "order.approved",
            {"order_id": run.input_data["order_id"]},
        )

        transition(run, "complete")

        return {
            "approved": True,
            "status": "completed",
            "reason": "All independent checks passed",
        }

    approval_task.status = TaskStatus.SKIPPED
    approval_task.error = "One or more prerequisite checks failed"

    transition(run, "fail")

    return {
        "approved": False,
        "status": "needs_review",
        "reason": "One or more independent checks failed",
    }


def run_parallel_workflow() -> dict[str, Any]:
    """Run the deterministic happy-path parallel workflow."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run = build_topic_fixture()

    workflow_input = WorkflowInput(**run.input_data)

    transition(run, "start")

    started_at = time.perf_counter()

    parallel_summary = execute_parallel_checks(
        run,
        workflow_input,
    )

    approval = approve_after_fan_in(
        run,
        parallel_summary["results"],
    )

    total_elapsed_ms = (time.perf_counter() - started_at) * 1000

    report = {
        "task": "Task 2 - Parallel Workflow Implementation",
        "run_id": run.run_id,
        "business_key": run.business_key,
        "workflow_state": run.state.value,
        "execution_pattern": {
            "fan_out": True,
            "worker_pool": "ThreadPoolExecutor",
            "synchronization": "wait(ALL_COMPLETED)",
            "fan_in": True,
        },
        "parallel_checks": parallel_summary,
        "approval": approval,
        "total_elapsed_ms": round(total_elapsed_ms, 3),
        "task_states": {
            task.task_id: task.status.value
            for task in run.tasks
        },
        "event_count": len(run.events),
        "trace_count": len(run.traces),
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("=" * 65)
    print("TASK 2 - PARALLEL WORKFLOW IMPLEMENTATION")
    print("=" * 65)
    print(json.dumps(report, indent=4))
    print(f"\nEvidence saved: {OUTPUT_FILE}")

    return report


if __name__ == "__main__":
    run_parallel_workflow()
