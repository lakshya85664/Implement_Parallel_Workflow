# Implement Parallel Workflow in Code

## Project overview
This project implements an order-validation workflow in which three independent checks—credit, inventory, and delivery address—run concurrently. The workflow uses a fan-out/fan-in pattern: the checks start independently, their results are collected, and order approval runs only after all required checks succeed.

## Scenario
- Order: `ORDER-1001`
- Customer: `CUSTOMER-501`
- SKU: `LAPTOP-15`
- Quantity: `1`
- Independent checks: credit, inventory, and address
- Final dependent task: order approval

## Project structure
```text
Implement_Parallel_Workflow/
├── parallel_workflow.py
├── parallel_executor.py
├── reliability.py
├── adapters.py
├── runbook.py
├── tests/
│   ├── test_workflow_contract.py
│   ├── test_parallel_execution.py
│   ├── test_failure_recovery.py
│   ├── test_integration_observability.py
│   └── test_operator_runbook.py
├── docs/state_transition.md
├── outputs/
├── traces/
└── reports/
    ├── OPERATOR_RUNBOOK.md
    └── evidence_report.json
```

## Architecture and implementation
1. **Workflow contract and state model:** defines the order workflow, task dependencies, legal workflow states, and task statuses.
2. **Parallel execution:** uses `ThreadPoolExecutor` to run credit, inventory, and address checks concurrently. A fan-in synchronization step waits for the independent checks before deciding whether approval can proceed.
3. **Failure and replay safety:** demonstrates retry handling for transient failures, avoids retrying permanent failures, handles malformed responses, and uses idempotency keys to prevent duplicate side effects.
4. **Integration and observability:** isolates external interactions behind injectable adapters and records structured traces and measurement data. Sensitive values are redacted from observable details.
5. **Operator runbook and evidence:** generates operator instructions and validates the expected JSON evidence files.

## Run the project (Windows CMD)
```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -v
```

Run demonstrations:
```cmd
python parallel_workflow.py
python parallel_executor.py
python reliability.py
python adapters.py
python runbook.py
```

Generated evidence is stored in `outputs/`, `traces/`, and `reports/`.

## Verification
The completed test suite was run using `python -m pytest -q`.

**Verified result: 56 passed.**
- Task 1: 8 passed
- Task 2: 10 passed
- Task 3: 15 passed
- Task 4: 14 passed
- Task 5: 9 passed

The final evidence inspection found all 7 expected files and validated all 7 as JSON. The report recorded `Evidence complete: True`.

## Limitations
This is a local demonstration using synthetic order data and fake/injectable adapters, not live external services. Thread-based execution provides concurrency, but Python cannot forcibly terminate a worker thread that is already running. Production adapters should enforce client-level timeouts. Production idempotency should use durable shared storage with suitable concurrency controls.

## Reflection
Building this parallel workflow helped me understand how independent operations can be coordinated without executing them one after another. I began by defining the workflow contract and state model, which made task dependencies and valid state transitions explicit. This was important because parallel execution becomes difficult to reason about when the workflow does not have a clear contract.

The parallel executor was the most practical part of the work. I used a thread pool to start the credit, inventory, and address checks independently, then added a fan-in step so approval could only happen after the required results were available. This demonstrated the difference between launching tasks concurrently and safely coordinating their completion.

The reliability tasks helped me think beyond the successful path. I implemented retry behavior for transient errors, avoided retrying permanent failures, handled malformed responses, and demonstrated idempotency to protect against duplicate side effects. I also learned that retrying is not a substitute for timeouts or safe integration design. In particular, a running Python thread cannot simply be force-stopped, so real service adapters need their own timeout controls.

Finally, I added adapter boundaries, structured traces, redaction, measurement output, and an operator runbook. These pieces made the workflow easier to inspect and troubleshoot. The evidence report also gave me a repeatable way to check whether the expected artifacts were present and valid.

The full test suite finished with 56 passing tests, and all seven expected evidence files were found and validated. Overall, this activity improved my understanding of fan-out/fan-in orchestration, failure handling, replay safety, observability, and the operational documentation needed to make a workflow maintainable.
