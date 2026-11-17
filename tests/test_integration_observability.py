
import pytest

from adapters import (
    AddressAdapter,
    CreditAdapter,
    IntegrationBoundary,
    InventoryAdapter,
    WorkflowMetrics,
    build_default_boundary,
    redact_sensitive,
    run_integration_demo,
)

from parallel_workflow import WorkflowInput


def make_input():
    return WorkflowInput(
        business_key="ORDER-TEST",
        order_id="ORDER-TEST",
        customer_id="CUSTOMER-TEST",
        sku="LAPTOP-15",
        quantity=1,
        delivery_address="Synthetic Address",
    )


def test_credit_adapter_success():
    response = CreditAdapter().execute(make_input())

    assert response["success"] is True
    assert response["credit_eligible"] is True


def test_inventory_adapter_success():
    response = InventoryAdapter().execute(make_input())

    assert response["success"] is True
    assert response["available_quantity"] == 10


def test_address_adapter_success():
    response = AddressAdapter().execute(make_input())

    assert response["success"] is True
    assert response["address_valid"] is True


def test_boundary_injects_adapter():
    boundary = build_default_boundary()

    response = boundary.execute(
        "RUN-1",
        "TASK-CREDIT",
        make_input(),
    )

    assert response["success"] is True
    assert boundary.metrics.total_calls == 1


def test_boundary_rejects_unknown_adapter():
    boundary = build_default_boundary()

    with pytest.raises(ValueError, match="No adapter"):
        boundary.execute(
            "RUN-1",
            "TASK-UNKNOWN",
            make_input(),
        )


def test_boundary_records_structured_trace():
    boundary = build_default_boundary()

    boundary.execute(
        "RUN-1",
        "TASK-CREDIT",
        make_input(),
    )

    assert len(boundary.traces) == 1

    trace = boundary.traces[0]

    assert trace.run_id == "RUN-1"
    assert trace.task_id == "TASK-CREDIT"
    assert trace.service == "credit_service"
    assert trace.outcome == "success"
    assert trace.duration_ms >= 0


def test_metrics_count_successful_tasks():
    metrics = WorkflowMetrics()

    metrics.record_task(True, 10)
    metrics.record_task(True, 20)

    report = metrics.report()

    assert report["task_successes"] == 2
    assert report["task_failures"] == 0
    assert report["total_service_calls"] == 2
    assert report["average_latency_ms"] == 15


def test_metrics_count_failed_tasks():
    metrics = WorkflowMetrics()

    metrics.record_task(False, 10)

    report = metrics.report()

    assert report["task_failures"] == 1
    assert report["task_successes"] == 0


def test_metrics_track_max_latency():
    metrics = WorkflowMetrics()

    metrics.record_task(True, 10)
    metrics.record_task(True, 30)

    assert metrics.report()["max_latency_ms"] == 30


def test_sensitive_fields_are_redacted():
    data = {
        "username": "synthetic-user",
        "password": "secret-value",
        "api_key": "key-value",
        "nested": {
            "access_token": "token-value",
        },
    }

    redacted = redact_sensitive(data)

    assert redacted["username"] == "synthetic-user"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["access_token"] == "[REDACTED]"


def test_sensitive_values_are_not_exposed_in_trace():
    class SecretAdapter:
        service_name = "secret_test_service"

        def execute(self, workflow_input):
            return {
                "success": True,
                "password": "do-not-log-this",
                "api_key": "hidden-key",
            }

    boundary = IntegrationBoundary({
        "TASK-CREDIT": SecretAdapter()
    })

    response = boundary.execute(
        "RUN-SECRET",
        "TASK-CREDIT",
        make_input(),
    )

    assert response["password"] == "[REDACTED]"
    assert response["api_key"] == "[REDACTED]"

    trace_text = str(boundary.traces[0].details)

    assert "do-not-log-this" not in trace_text
    assert "hidden-key" not in trace_text


def test_adapter_exception_is_observable():
    class BrokenAdapter:
        service_name = "broken_service"

        def execute(self, workflow_input):
            raise ConnectionError("synthetic dependency failure")

    boundary = IntegrationBoundary({
        "TASK-CREDIT": BrokenAdapter()
    })

    response = boundary.execute(
        "RUN-ERROR",
        "TASK-CREDIT",
        make_input(),
    )

    assert response["success"] is False
    assert response["error"] == "ConnectionError"
    assert boundary.traces[0].outcome == "error"
    assert boundary.metrics.task_failures == 1


def test_empty_adapter_registry_is_rejected():
    with pytest.raises(ValueError, match="At least one"):
        IntegrationBoundary({})


def test_demo_generates_observability_evidence():
    report = run_integration_demo()

    assert report["workflow_success"] is True
    assert report["trace_count"] == 3
    assert report["metrics"]["task_successes"] == 3
    assert report["metrics"]["workflow_completions"] == 1
