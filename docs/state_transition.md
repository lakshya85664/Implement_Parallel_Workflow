
# Parallel Workflow State Transition Model

## Workflow States

| Current state | Event | Next state | Meaning |
|---|---|---|---|
| created | start | running | Workflow execution begins |
| running | complete | completed | All required workflow activities succeeded |
| running | pause | waiting | Workflow is waiting for an external condition |
| waiting | resume | running | Workflow resumes |
| running | fail | needs_review | Workflow requires operator review |
| waiting | fail | needs_review | Waiting workflow requires operator review |

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> created
    created --> running: start
    running --> completed: complete
    running --> waiting: pause
    waiting --> running: resume
    running --> needs_review: fail
    waiting --> needs_review: fail
    completed --> [*]
    needs_review --> [*]
```

## Parallel Check Design

The order workflow contains three independent checks:

- Credit check
- Inventory check
- Address check

All three checks are prerequisites for the approval task.

```mermaid
flowchart TD
    A[Order Submitted] --> B[Credit Check]
    A --> C[Inventory Check]
    A --> D[Address Check]
    B --> E{Fan-in: All Results}
    C --> E
    D --> E
    E -->|All Valid| F[Approve Order]
    E -->|Any Failure| G[Reject or Needs Review]
```

The parallel execution mechanism will be implemented in Task 2.
