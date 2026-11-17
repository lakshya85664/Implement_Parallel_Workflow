
"""
Topic 4 - Implement Parallel Workflow in Code
Task 1 - Workflow Contract and State Model

This module defines typed workflow models and legal state transitions.
Parallel execution will be implemented in Task 2.
"""

from __future__ import annotations

import json
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "task1_workflow_contract.json"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowInput:
    """Validated synthetic business input for an order."""

    business_key: str
    order_id: str
    customer_id: str
    sku: str
    quantity: int
    delivery_address: str

    def __post_init__(self) -> None:
        required_fields = {
            "business_key": self.business_key,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "sku": self.sku,
            "delivery_address": self.delivery_address,
        }

        for field_name, value in required_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise ValueError("quantity must be an integer")

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")


@dataclass
class WorkflowTask:
    """Represents one independent or dependent workflow task."""

    task_id: str
    name: str
    owner: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    attempts: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class WorkflowEvent:
    """Represents a state or task event."""

    event_id: str
    run_id: str
    event_type: str
    state: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Standard result returned by an individual workflow task."""

    task_id: str
    success: bool
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class WorkflowTrace:
    """Structured trace for an execution or side effect."""

    trace_id: str
    run_id: str
    task_id: str
    operation: str
    outcome: str
    timestamp: str
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowRun:
    """Top-level workflow execution state."""

    run_id: str
    business_key: str
    state: WorkflowState = WorkflowState.CREATED
    attempts: int = 0
    input_data: dict[str, Any] = field(default_factory=dict)
    tasks: list[WorkflowTask] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
    traces: list[WorkflowTrace] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def record(
        self,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            run_id=self.run_id,
            event_type=event_type,
            state=self.state.value,
            timestamp=utc_now(),
            details=details or {},
        )

        self.events.append(event)
        self.updated_at = event.timestamp
        return event

    def add_trace(
        self,
        task_id: str,
        operation: str,
        outcome: str,
        duration_ms: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> WorkflowTrace:
        trace = WorkflowTrace(
            trace_id=str(uuid.uuid4()),
            run_id=self.run_id,
            task_id=task_id,
            operation=operation,
            outcome=outcome,
            timestamp=utc_now(),
            duration_ms=duration_ms,
            details=details or {},
        )

        self.traces.append(trace)
        return trace


LEGAL_TRANSITIONS: dict[tuple[WorkflowState, str], WorkflowState] = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "complete"): WorkflowState.COMPLETED,
    (WorkflowState.RUNNING, "pause"): WorkflowState.WAITING,
    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "fail"): WorkflowState.NEEDS_REVIEW,
    (WorkflowState.WAITING, "fail"): WorkflowState.NEEDS_REVIEW,
}


def transition(
    run: WorkflowRun,
    event: str,
) -> WorkflowRun:
    """
    Apply a legal state transition.

    Raises ValueError when the requested transition is not allowed.
    """

    current_state = run.state
    next_state = LEGAL_TRANSITIONS.get((current_state, event))

    if next_state is None:
        raise ValueError(
            f"Illegal workflow transition: "
            f"{current_state.value} + {event}"
        )

    run.state = next_state
    run.updated_at = utc_now()

    run.record(
        event_type=event,
        details={
            "previous_state": current_state.value,
            "next_state": next_state.value,
        },
    )

    return run


def build_topic_fixture() -> WorkflowRun:
    """Build a synthetic order workflow with three independent checks."""

    workflow_input = WorkflowInput(
        business_key="ORDER-1001",
        order_id="ORDER-1001",
        customer_id="CUSTOMER-501",
        sku="LAPTOP-15",
        quantity=1,
        delivery_address="Synthetic Address, Jaipur",
    )

    tasks = [
        WorkflowTask(
            task_id="TASK-CREDIT",
            name="credit_check",
            owner="credit_service",
        ),
        WorkflowTask(
            task_id="TASK-INVENTORY",
            name="inventory_check",
            owner="inventory_service",
        ),
        WorkflowTask(
            task_id="TASK-ADDRESS",
            name="address_check",
            owner="address_service",
        ),
        WorkflowTask(
            task_id="TASK-APPROVAL",
            name="approve_order",
            owner="order_service",
            dependencies=[
                "TASK-CREDIT",
                "TASK-INVENTORY",
                "TASK-ADDRESS",
            ],
        ),
    ]

    run = WorkflowRun(
        run_id="RUN-TOPIC4-001",
        business_key=workflow_input.business_key,
        input_data=asdict(workflow_input),
        tasks=tasks,
    )

    run.record(
        event_type="workflow.created",
        details={
            "scenario": "parallel_order_checks",
            "independent_checks": [
                "credit_check",
                "inventory_check",
                "address_check",
            ],
            "approval_dependency": [
                "TASK-CREDIT",
                "TASK-INVENTORY",
                "TASK-ADDRESS",
            ],
        },
    )

    return run


def save_fixture(run: WorkflowRun) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = asdict(run)
    data["state"] = run.state.value

    for task in data["tasks"]:
        task["status"] = task["status"].value

    OUTPUT_FILE.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )


def run_task1_demo() -> dict[str, Any]:
    run = build_topic_fixture()

    transition(run, "start")

    save_fixture(run)

    result = {
        "task": "Task 1 - Workflow Contract and State Model",
        "run_id": run.run_id,
        "business_key": run.business_key,
        "workflow_state": run.state.value,
        "tasks": [
            {
                "task_id": task.task_id,
                "name": task.name,
                "owner": task.owner,
                "status": task.status.value,
                "dependencies": task.dependencies,
            }
            for task in run.tasks
        ],
        "legal_transitions": [
            {
                "from": source.value,
                "event": event,
                "to": destination.value,
            }
            for (source, event), destination in LEGAL_TRANSITIONS.items()
        ],
        "event_count": len(run.events),
        "trace_count": len(run.traces),
        "evidence_file": str(OUTPUT_FILE.relative_to(BASE_DIR)),
    }

    print("=" * 65)
    print("TOPIC 4 - TASK 1: WORKFLOW CONTRACT AND STATE MODEL")
    print("=" * 65)
    print(json.dumps(result, indent=4))
    print(f"\nEvidence saved: {OUTPUT_FILE}")

    return result


if __name__ == "__main__":
    run_task1_demo()
