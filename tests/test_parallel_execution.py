
import pytest

from parallel_executor import (
    approve_after_fan_in,
    execute_parallel_checks,
    run_parallel_workflow,
)
from parallel_workflow import (
    WorkflowInput,
    WorkflowState,
    build_topic_fixture,
    transition,
)


def make_input():
    return WorkflowInput(
        business_key="ORDER-TEST",
        order_id="ORDER-TEST",
        customer_id="CUSTOMER-TEST",
        sku="LAPTOP-15",
        quantity=1,
        delivery_address="Synthetic Address",
    )


def test_parallel_workflow_happy_path():
    report = run_parallel_workflow()

    assert report["workflow_state"] == "completed"
    assert report["approval"]["approved"] is True
    assert report["parallel_checks"]["success_count"] == 3
    assert report["parallel_checks"]["failure_count"] == 0


def test_all_three_checks_are_executed():
    run = build_topic_fixture()
    transition(run, "start")

    summary = execute_parallel_checks(run, make_input())

    assert set(summary["results"]) == {
        "TASK-CREDIT",
        "TASK-INVENTORY",
        "TASK-ADDRESS",
    }


def test_parallel_checks_return_success():
    run = build_topic_fixture()
    transition(run, "start")

    summary = execute_parallel_checks(run, make_input())

    assert summary["success_count"] == 3
    assert summary["failure_count"] == 0


def test_fan_in_approves_only_after_all_checks_pass():
    run = build_topic_fixture()
    transition(run, "start")

    summary = execute_parallel_checks(run, make_input())

    approval = approve_after_fan_in(run, summary["results"])

    assert approval["approved"] is True
    assert run.state == WorkflowState.COMPLETED


def test_fan_in_rejects_when_one_check_fails():
    run = build_topic_fixture()
    transition(run, "start")

    results = {
        "TASK-CREDIT": {"success": True},
        "TASK-INVENTORY": {"success": False},
        "TASK-ADDRESS": {"success": True},
    }

    approval = approve_after_fan_in(run, results)

    assert approval["approved"] is False
    assert run.state == WorkflowState.NEEDS_REVIEW


def test_fan_in_rejects_incomplete_results():
    run = build_topic_fixture()
    transition(run, "start")

    incomplete_results = {
        "TASK-CREDIT": {"success": True},
        "TASK-INVENTORY": {"success": True},
    }

    with pytest.raises(ValueError, match="all three"):
        approve_after_fan_in(run, incomplete_results)


def test_worker_limit_must_be_positive():
    run = build_topic_fixture()
    transition(run, "start")

    with pytest.raises(ValueError, match="max_workers"):
        execute_parallel_checks(
            run,
            make_input(),
            max_workers=0,
        )


def test_timeout_must_be_positive():
    run = build_topic_fixture()
    transition(run, "start")

    with pytest.raises(ValueError, match="timeout_seconds"):
        execute_parallel_checks(
            run,
            make_input(),
            timeout_seconds=0,
        )


def test_parallel_execution_records_task_traces():
    run = build_topic_fixture()
    transition(run, "start")

    execute_parallel_checks(run, make_input())

    assert len(run.traces) == 3
    assert all(
        trace.operation == "parallel_check"
        for trace in run.traces
    )


def test_parallel_tasks_are_marked_succeeded():
    run = build_topic_fixture()
    transition(run, "start")

    execute_parallel_checks(run, make_input())

    statuses = {
        task.task_id: task.status.value
        for task in run.tasks
    }

    assert statuses["TASK-CREDIT"] == "succeeded"
    assert statuses["TASK-INVENTORY"] == "succeeded"
    assert statuses["TASK-ADDRESS"] == "succeeded"
