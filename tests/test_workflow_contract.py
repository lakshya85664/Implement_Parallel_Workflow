
import pytest

from parallel_workflow import (
    WorkflowInput,
    WorkflowState,
    build_topic_fixture,
    transition,
)


def test_created_to_running_is_legal():
    run = build_topic_fixture()

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING
    assert run.events[-1].event_type == "start"
    assert run.events[-1].details["previous_state"] == "created"
    assert run.events[-1].details["next_state"] == "running"


def test_created_to_completed_is_illegal():
    run = build_topic_fixture()

    with pytest.raises(ValueError, match="Illegal workflow transition"):
        transition(run, "complete")

    assert run.state == WorkflowState.CREATED


def test_fixture_has_three_independent_checks():
    run = build_topic_fixture()

    checks = [
        task for task in run.tasks
        if task.name in {
            "credit_check",
            "inventory_check",
            "address_check",
        }
    ]

    assert len(checks) == 3
    assert all(task.dependencies == [] for task in checks)


def test_approval_depends_on_all_three_checks():
    run = build_topic_fixture()

    approval = next(
        task for task in run.tasks
        if task.name == "approve_order"
    )

    assert set(approval.dependencies) == {
        "TASK-CREDIT",
        "TASK-INVENTORY",
        "TASK-ADDRESS",
    }


def test_input_rejects_empty_business_key():
    with pytest.raises(ValueError, match="business_key"):
        WorkflowInput(
            business_key="",
            order_id="ORDER-1",
            customer_id="CUSTOMER-1",
            sku="SKU-1",
            quantity=1,
            delivery_address="Synthetic Address",
        )


def test_input_rejects_non_positive_quantity():
    with pytest.raises(ValueError, match="greater than zero"):
        WorkflowInput(
            business_key="ORDER-1",
            order_id="ORDER-1",
            customer_id="CUSTOMER-1",
            sku="SKU-1",
            quantity=0,
            delivery_address="Synthetic Address",
        )


def test_workflow_records_events():
    run = build_topic_fixture()

    assert len(run.events) == 1
    assert run.events[0].event_type == "workflow.created"
    assert run.events[0].run_id == run.run_id


def test_workflow_fixture_has_unique_task_ids():
    run = build_topic_fixture()

    task_ids = [task.task_id for task in run.tasks]

    assert len(task_ids) == len(set(task_ids))
