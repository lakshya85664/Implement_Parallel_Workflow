# Topic 4 — Parallel Workflow Operator Runbook

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

`E:\Tayana_Projects\Workflow_Orchestration\Implement_Parallel_Workflow`

Activate the virtual environment:

```cmd
.venv\Scripts\activate
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
