
import pytest

from reliability import (
    IdempotencyStore,
    MalformedResponseError,
    PermanentError,
    RetryExecutor,
    RetryPolicy,
    TransientError,
    WorkflowTriggerGuard,
    execute_with_timeout,
)


def no_sleep(_):
    """Keep retry tests deterministic and fast."""


def test_transient_failure_retries_until_success():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1

        if calls["count"] < 3:
            raise TransientError("temporary issue")

        return {"success": True}

    executor = RetryExecutor(
        RetryPolicy(max_attempts=3, backoff_seconds=[0, 0]),
        sleeper=no_sleep,
    )

    result = executor.execute("TASK-1", operation)

    assert result.success is True
    assert result.attempts == 3
    assert calls["count"] == 3


def test_retry_trace_records_each_attempt():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1

        if calls["count"] == 1:
            raise TransientError("temporary issue")

        return {"success": True}

    executor = RetryExecutor(
        RetryPolicy(max_attempts=3, backoff_seconds=[0, 0]),
        sleeper=no_sleep,
    )

    executor.execute("TASK-1", operation)

    assert len(executor.trace) == 2
    assert executor.trace[0]["outcome"] == "transient_failure"
    assert executor.trace[1]["outcome"] == "success"


def test_transient_failure_stops_after_max_attempts():
    executor = RetryExecutor(
        RetryPolicy(max_attempts=2, backoff_seconds=[0]),
        sleeper=no_sleep,
    )

    result = executor.execute(
        "TASK-1",
        lambda: (_ for _ in ()).throw(
            TransientError("service unavailable")
        ),
    )

    assert result.success is False
    assert result.status == "retry_exhausted"
    assert result.attempts == 2
    assert result.next_action == "operator_review"


def test_permanent_failure_is_not_retried():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        raise PermanentError("not eligible")

    executor = RetryExecutor(sleeper=no_sleep)
    result = executor.execute("TASK-2", operation)

    assert result.status == "permanent_failure"
    assert result.attempts == 1
    assert calls["count"] == 1
    assert result.next_action == "operator_review"


def test_malformed_response_is_quarantined():
    executor = RetryExecutor(sleeper=no_sleep)

    result = executor.execute(
        "TASK-3",
        lambda: {"wrong_field": True},
    )

    assert result.status == "malformed_response"
    assert result.attempts == 1
    assert result.next_action == "quarantine_response"


def test_non_dictionary_response_is_rejected():
    executor = RetryExecutor(sleeper=no_sleep)

    result = executor.execute(
        "TASK-3",
        lambda: ["invalid"],
    )

    assert result.status == "malformed_response"


def test_timeout_returns_explicit_recovery_action():
    result = execute_with_timeout(
        lambda: __import__("time").sleep(0.2) or {"success": True},
        timeout_seconds=0.01,
    )

    assert result.status == "timeout"
    assert result.success is False
    assert result.next_action == "retry_or_operator_review"


def test_timeout_must_be_positive():
    with pytest.raises(ValueError, match="timeout_seconds"):
        execute_with_timeout(
            lambda: {"success": True},
            timeout_seconds=0,
        )


def test_idempotency_prevents_duplicate_side_effect():
    store = IdempotencyStore()
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        return {"account_id": "ACC-1"}

    first = store.execute("KEY-1", operation)
    second = store.execute("KEY-1", operation)

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert calls["count"] == 1
    assert store.side_effect_count == 1


def test_different_idempotency_keys_execute_independently():
    store = IdempotencyStore()
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        return {"created": True}

    store.execute("KEY-1", operation)
    store.execute("KEY-2", operation)

    assert calls["count"] == 2
    assert store.side_effect_count == 2


def test_idempotency_rejects_empty_key():
    store = IdempotencyStore()

    with pytest.raises(ValueError, match="idempotency_key"):
        store.execute("", lambda: {"created": True})


def test_duplicate_workflow_trigger_is_blocked():
    guard = WorkflowTriggerGuard()

    first = guard.start("ORDER-1")
    second = guard.start("ORDER-1")

    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["duplicate"] is True
    assert first["run_id"] == second["run_id"]


def test_different_business_keys_create_different_runs():
    guard = WorkflowTriggerGuard()

    first = guard.start("ORDER-1")
    second = guard.start("ORDER-2")

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert first["run_id"] != second["run_id"]


def test_retry_policy_rejects_invalid_attempt_count():
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)


def test_retry_policy_rejects_negative_backoff():
    with pytest.raises(ValueError, match="negative"):
        RetryPolicy(
            max_attempts=2,
            backoff_seconds=[-1],
        )
