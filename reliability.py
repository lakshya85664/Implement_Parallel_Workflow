
"""
Topic 4 - Task 3: Failure, Retry, and Replay Safety

Demonstrates:
- Error classification.
- Bounded retry with backoff.
- Timeout result handling.
- Malformed response validation.
- Idempotent side-effect protection.
- Duplicate workflow trigger protection.
- Structured retry and recovery evidence.
"""

from __future__ import annotations

import json
import time
import uuid

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, asdict, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
TRACE_DIR = BASE_DIR / "traces"

OUTPUT_FILE = OUTPUT_DIR / "task3_failure_recovery.json"
TRACE_FILE = TRACE_DIR / "task3_retry_trace.json"


class TransientError(Exception):
    """An error that may succeed when retried."""


class PermanentError(Exception):
    """An error that should not be retried."""


class MalformedResponseError(Exception):
    """An external service returned an invalid response."""


class TaskTimeoutError(Exception):
    """A task did not return within its configured time."""


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: list[float] = field(
        default_factory=lambda: [0.1, 0.2]
    )

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if any(delay < 0 for delay in self.backoff_seconds):
            raise ValueError("Backoff delays cannot be negative")


@dataclass
class RecoveryResult:
    success: bool
    status: str
    attempts: int
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    next_action: str = "none"


class RetryExecutor:
    """Execute a callable with bounded retries and error classification."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.policy = policy or RetryPolicy()
        self.sleeper = sleeper
        self.trace: list[dict[str, Any]] = []

    def execute(
        self,
        task_id: str,
        operation: Callable[[], Any],
    ) -> RecoveryResult:

        for attempt in range(1, self.policy.max_attempts + 1):
            started = time.perf_counter()

            try:
                response = operation()

                if not isinstance(response, dict):
                    raise MalformedResponseError(
                        "Response must be a dictionary"
                    )

                if "success" not in response:
                    raise MalformedResponseError(
                        "Response is missing success field"
                    )

                if not isinstance(response["success"], bool):
                    raise MalformedResponseError(
                        "success must be a boolean"
                    )

                if not response["success"]:
                    raise PermanentError(
                        response.get("error", "Operation rejected")
                    )

                self._record(
                    task_id,
                    attempt,
                    "success",
                    started,
                )

                return RecoveryResult(
                    success=True,
                    status="succeeded",
                    attempts=attempt,
                    result=response,
                )

            except TransientError as exc:
                self._record(
                    task_id,
                    attempt,
                    "transient_failure",
                    started,
                    str(exc),
                )

                if attempt == self.policy.max_attempts:
                    return RecoveryResult(
                        success=False,
                        status="retry_exhausted",
                        attempts=attempt,
                        error=str(exc),
                        next_action="operator_review",
                    )

                delay_index = min(
                    attempt - 1,
                    len(self.policy.backoff_seconds) - 1,
                )

                delay = self.policy.backoff_seconds[delay_index]

                self.trace[-1]["backoff_seconds"] = delay
                self.sleeper(delay)

            except PermanentError as exc:
                self._record(
                    task_id,
                    attempt,
                    "permanent_failure",
                    started,
                    str(exc),
                )

                return RecoveryResult(
                    success=False,
                    status="permanent_failure",
                    attempts=attempt,
                    error=str(exc),
                    next_action="operator_review",
                )

            except MalformedResponseError as exc:
                self._record(
                    task_id,
                    attempt,
                    "malformed_response",
                    started,
                    str(exc),
                )

                return RecoveryResult(
                    success=False,
                    status="malformed_response",
                    attempts=attempt,
                    error=str(exc),
                    next_action="quarantine_response",
                )

            except Exception as exc:
                self._record(
                    task_id,
                    attempt,
                    "unexpected_failure",
                    started,
                    str(exc),
                )

                return RecoveryResult(
                    success=False,
                    status="unexpected_failure",
                    attempts=attempt,
                    error=type(exc).__name__,
                    next_action="operator_review",
                )

        raise RuntimeError("Retry loop ended unexpectedly")

    def _record(
        self,
        task_id: str,
        attempt: int,
        outcome: str,
        started: float,
        error: str | None = None,
    ) -> None:
        self.trace.append({
            "trace_id": str(uuid.uuid4()),
            "task_id": task_id,
            "attempt": attempt,
            "outcome": outcome,
            "duration_ms": round(
                (time.perf_counter() - started) * 1000,
                3,
            ),
            "error": error,
            "timestamp": time.time(),
        })


def execute_with_timeout(
    operation: Callable[[], Any],
    timeout_seconds: float,
) -> RecoveryResult:
    """
    Return a timeout result when the operation exceeds its deadline.

    A running Python thread cannot be forcibly terminated. Real adapters
    must also configure network/client-level timeouts to bound the work.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    executor = ThreadPoolExecutor(max_workers=1)

    future = executor.submit(operation)

    try:
        response = future.result(timeout=timeout_seconds)

        if not isinstance(response, dict):
            raise MalformedResponseError(
                "Response must be a dictionary"
            )

        if response.get("success") is not True:
            raise PermanentError(
                response.get("error", "Operation failed")
            )

        return RecoveryResult(
            success=True,
            status="succeeded",
            attempts=1,
            result=response,
        )

    except TimeoutError:
        future.cancel()

        return RecoveryResult(
            success=False,
            status="timeout",
            attempts=1,
            error="Task exceeded configured timeout",
            next_action="retry_or_operator_review",
        )

    except MalformedResponseError as exc:
        return RecoveryResult(
            success=False,
            status="malformed_response",
            attempts=1,
            error=str(exc),
            next_action="quarantine_response",
        )

    except PermanentError as exc:
        return RecoveryResult(
            success=False,
            status="permanent_failure",
            attempts=1,
            error=str(exc),
            next_action="operator_review",
        )

    except Exception as exc:
        return RecoveryResult(
            success=False,
            status="unexpected_failure",
            attempts=1,
            error=type(exc).__name__,
            next_action="operator_review",
        )

    finally:
        # Do not wait indefinitely for an already running thread.
        executor.shutdown(wait=False, cancel_futures=True)


class IdempotencyStore:
    """
    In-memory idempotency store for synthetic side-effect protection.

    A repeated key returns the original result without repeating
    the side effect.
    """

    def __init__(self):
        self._results: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.side_effect_count = 0

    def execute(
        self,
        idempotency_key: str,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:

        if not idempotency_key.strip():
            raise ValueError("idempotency_key cannot be empty")

        with self._lock:
            if idempotency_key in self._results:
                return {
                    "replayed": True,
                    "result": self._results[idempotency_key],
                }

            result = operation()

            if not isinstance(result, dict):
                raise MalformedResponseError(
                    "Idempotent operation must return a dictionary"
                )

            self.side_effect_count += 1
            self._results[idempotency_key] = result

            return {
                "replayed": False,
                "result": result,
            }


class WorkflowTriggerGuard:
    """Prevent duplicate workflow runs for the same business key."""

    def __init__(self):
        self._runs: dict[str, str] = {}
        self._lock = Lock()

    def start(self, business_key: str) -> dict[str, Any]:
        if not business_key.strip():
            raise ValueError("business_key cannot be empty")

        with self._lock:
            if business_key in self._runs:
                return {
                    "accepted": False,
                    "duplicate": True,
                    "run_id": self._runs[business_key],
                }

            run_id = str(uuid.uuid4())
            self._runs[business_key] = run_id

            return {
                "accepted": True,
                "duplicate": False,
                "run_id": run_id,
            }


def run_failure_recovery_demo() -> dict[str, Any]:
    """Generate deterministic examples for assessment evidence."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Transient failure, then success.
    calls = {"count": 0}

    def transient_operation():
        calls["count"] += 1

        if calls["count"] < 3:
            raise TransientError("Temporary dependency failure")

        return {"success": True, "account_id": "ACC-ORDER-1001"}

    retry_executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            backoff_seconds=[0.1, 0.2],
        ),
        sleeper=lambda _: None,
    )

    transient_result = retry_executor.execute(
        "TASK-CREDIT",
        transient_operation,
    )

    # 2. Permanent failure is not retried.
    permanent_executor = RetryExecutor(
        sleeper=lambda _: None
    )

    permanent_result = permanent_executor.execute(
        "TASK-INVENTORY",
        lambda: (_ for _ in ()).throw(
            PermanentError("Insufficient stock")
        ),
    )

    # 3. Malformed response is quarantined.
    malformed_executor = RetryExecutor(
        sleeper=lambda _: None
    )

    malformed_result = malformed_executor.execute(
        "TASK-ADDRESS",
        lambda: {"unexpected": "payload"},
    )

    # 4. Timeout.
    timeout_result = execute_with_timeout(
        lambda: (time.sleep(0.2) or {"success": True}),
        timeout_seconds=0.02,
    )

    # 5. Idempotent side effect.
    idempotency_store = IdempotencyStore()

    def create_account():
        return {
            "account_id": "ACC-ORDER-1001",
            "created": True,
        }

    first_call = idempotency_store.execute(
        "ORDER-1001-CREATE-ACCOUNT",
        create_account,
    )

    replay_call = idempotency_store.execute(
        "ORDER-1001-CREATE-ACCOUNT",
        create_account,
    )

    # 6. Duplicate workflow trigger.
    trigger_guard = WorkflowTriggerGuard()

    first_trigger = trigger_guard.start("ORDER-1001")
    duplicate_trigger = trigger_guard.start("ORDER-1001")

    report = {
        "task": "Task 3 - Failure, Retry, and Replay Safety",
        "transient_failure": asdict(transient_result),
        "permanent_failure": asdict(permanent_result),
        "malformed_response": asdict(malformed_result),
        "timeout": asdict(timeout_result),
        "idempotency": {
            "first_call": first_call,
            "replay_call": replay_call,
            "side_effect_count": idempotency_store.side_effect_count,
        },
        "duplicate_trigger": {
            "first": first_trigger,
            "second": duplicate_trigger,
        },
        "retry_trace": retry_executor.trace,
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    TRACE_FILE.write_text(
        json.dumps(retry_executor.trace, indent=4),
        encoding="utf-8",
    )

    print("=" * 65)
    print("TASK 3 - FAILURE, RETRY, AND REPLAY SAFETY")
    print("=" * 65)
    print(json.dumps(report, indent=4))
    print(f"\nEvidence saved: {OUTPUT_FILE}")
    print(f"Retry trace saved: {TRACE_FILE}")

    return report


if __name__ == "__main__":
    run_failure_recovery_demo()
