
"""
Topic 4 - Task 4: Integration Boundary and Observability

Provides:
- Injectable service adapter protocol.
- Synthetic fake service adapters.
- Structured execution traces.
- Metrics collection.
- Sensitive-field redaction.
- JSON evidence and measurement reports.
"""

from __future__ import annotations

import json
import time
import uuid

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Protocol

from parallel_workflow import WorkflowInput


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
TRACE_DIR = BASE_DIR / "traces"

OUTPUT_FILE = OUTPUT_DIR / "task4_integration_observability.json"
TRACE_FILE = TRACE_DIR / "task4_observability_trace.json"
METRICS_FILE = OUTPUT_DIR / "task4_measurement_report.json"


SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "access_token",
    "refresh_token",
}


def redact_sensitive(data: Any) -> Any:
    """Recursively redact sensitive dictionary values."""

    if isinstance(data, dict):
        redacted = {}

        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive(value)

        return redacted

    if isinstance(data, list):
        return [redact_sensitive(item) for item in data]

    if isinstance(data, tuple):
        return [redact_sensitive(item) for item in data]

    return data


class ServiceAdapter(Protocol):
    """Contract implemented by external service adapters."""

    service_name: str

    def execute(
        self,
        workflow_input: WorkflowInput,
    ) -> dict[str, Any]:
        ...


class CreditAdapter:
    service_name = "credit_service"

    def execute(self, workflow_input: WorkflowInput) -> dict[str, Any]:
        return {
            "success": True,
            "customer_id": workflow_input.customer_id,
            "credit_eligible": True,
            "provider": "fake_credit_provider",
        }


class InventoryAdapter:
    service_name = "inventory_service"

    def execute(self, workflow_input: WorkflowInput) -> dict[str, Any]:
        available_quantity = 10

        return {
            "success": available_quantity >= workflow_input.quantity,
            "sku": workflow_input.sku,
            "available_quantity": available_quantity,
            "requested_quantity": workflow_input.quantity,
            "provider": "fake_inventory_provider",
        }


class AddressAdapter:
    service_name = "address_service"

    def execute(self, workflow_input: WorkflowInput) -> dict[str, Any]:
        valid = bool(workflow_input.delivery_address.strip())

        return {
            "success": valid,
            "address_valid": valid,
            "provider": "fake_address_provider",
        }


@dataclass
class AdapterTrace:
    trace_id: str
    run_id: str
    task_id: str
    service: str
    outcome: str
    timestamp: str
    duration_ms: float
    details: dict[str, Any] = field(default_factory=dict)


class WorkflowMetrics:
    """Collect basic workflow and integration measurements."""

    def __init__(self):
        self.workflow_starts = 0
        self.workflow_completions = 0
        self.workflow_failures = 0

        self.task_successes = 0
        self.task_failures = 0

        self.total_calls = 0
        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0

    def record_workflow_start(self):
        self.workflow_starts += 1

    def record_workflow_completion(self):
        self.workflow_completions += 1

    def record_workflow_failure(self):
        self.workflow_failures += 1

    def record_task(
        self,
        success: bool,
        duration_ms: float,
    ):
        self.total_calls += 1
        self.total_latency_ms += duration_ms
        self.max_latency_ms = max(
            self.max_latency_ms,
            duration_ms,
        )

        if success:
            self.task_successes += 1
        else:
            self.task_failures += 1

    def report(self) -> dict[str, Any]:
        average_latency = (
            self.total_latency_ms / self.total_calls
            if self.total_calls
            else 0.0
        )

        return {
            "workflow_starts": self.workflow_starts,
            "workflow_completions": self.workflow_completions,
            "workflow_failures": self.workflow_failures,
            "task_successes": self.task_successes,
            "task_failures": self.task_failures,
            "total_service_calls": self.total_calls,
            "total_latency_ms": round(self.total_latency_ms, 3),
            "average_latency_ms": round(average_latency, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
        }


class IntegrationBoundary:
    """
    Executes service adapters through an injectable boundary.

    The workflow does not need to know which external provider
    implements the adapter.
    """

    def __init__(
        self,
        adapters: dict[str, ServiceAdapter],
    ):
        if not adapters:
            raise ValueError("At least one adapter is required")

        self.adapters = adapters
        self.metrics = WorkflowMetrics()
        self.traces: list[AdapterTrace] = []

    def execute(
        self,
        run_id: str,
        task_id: str,
        workflow_input: WorkflowInput,
    ) -> dict[str, Any]:

        adapter = self.adapters.get(task_id)

        if adapter is None:
            raise ValueError(f"No adapter registered for {task_id}")

        started = time.perf_counter()
        timestamp = time.time()

        try:
            response = adapter.execute(workflow_input)

            if not isinstance(response, dict):
                raise ValueError("Adapter response must be a dictionary")

            if not isinstance(response.get("success"), bool):
                raise ValueError("Adapter response requires boolean success")

            outcome = (
                "success"
                if response["success"]
                else "failure"
            )

        except Exception as exc:
            response = {
                "success": False,
                "error": type(exc).__name__,
            }
            outcome = "error"

        duration_ms = (
            time.perf_counter() - started
        ) * 1000

        self.metrics.record_task(
            success=response.get("success") is True,
            duration_ms=duration_ms,
        )

        trace = AdapterTrace(
            trace_id=str(uuid.uuid4()),
            run_id=run_id,
            task_id=task_id,
            service=adapter.service_name,
            outcome=outcome,
            timestamp=str(timestamp),
            duration_ms=round(duration_ms, 3),
            details=redact_sensitive(response),
        )

        self.traces.append(trace)

        return redact_sensitive(response)


def build_default_boundary() -> IntegrationBoundary:
    """Create the synthetic adapter implementations."""

    return IntegrationBoundary({
        "TASK-CREDIT": CreditAdapter(),
        "TASK-INVENTORY": InventoryAdapter(),
        "TASK-ADDRESS": AddressAdapter(),
    })


def run_integration_demo() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    workflow_input = WorkflowInput(
        business_key="ORDER-4001",
        order_id="ORDER-4001",
        customer_id="CUSTOMER-4001",
        sku="LAPTOP-15",
        quantity=1,
        delivery_address="Synthetic Address, Jaipur",
    )

    boundary = build_default_boundary()
    boundary.metrics.record_workflow_start()

    task_mapping = {
        "TASK-CREDIT": "credit_check",
        "TASK-INVENTORY": "inventory_check",
        "TASK-ADDRESS": "address_check",
    }

    results = {}

    for task_id, task_name in task_mapping.items():
        results[task_name] = boundary.execute(
            run_id="RUN-TOPIC4-4001",
            task_id=task_id,
            workflow_input=workflow_input,
        )

    all_successful = all(
        result["success"]
        for result in results.values()
    )

    if all_successful:
        boundary.metrics.record_workflow_completion()
    else:
        boundary.metrics.record_workflow_failure()

    metrics = boundary.metrics.report()

    report = {
        "task": "Task 4 - Integration Boundary and Observability",
        "run_id": "RUN-TOPIC4-4001",
        "integration_type": "injectable_fake_adapters",
        "results": results,
        "workflow_success": all_successful,
        "metrics": metrics,
        "trace_count": len(boundary.traces),
        "traces": [
            asdict(trace)
            for trace in boundary.traces
        ],
        "secret_redaction_enabled": True,
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    TRACE_FILE.write_text(
        json.dumps(
            [asdict(trace) for trace in boundary.traces],
            indent=4,
        ),
        encoding="utf-8",
    )

    METRICS_FILE.write_text(
        json.dumps(metrics, indent=4),
        encoding="utf-8",
    )

    print("=" * 65)
    print("TASK 4 - INTEGRATION AND OBSERVABILITY")
    print("=" * 65)
    print(json.dumps(report, indent=4))
    print(f"\nEvidence saved: {OUTPUT_FILE}")
    print(f"Trace saved: {TRACE_FILE}")
    print(f"Metrics saved: {METRICS_FILE}")

    return report


if __name__ == "__main__":
    run_integration_demo()
