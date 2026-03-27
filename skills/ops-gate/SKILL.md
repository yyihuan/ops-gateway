---
name: ops-gate
description: Use when a task needs a safety gate for agent operations: route every non-basic action through structured plan review, explicit manual approval, and run-level evidence. Also use when reviewing or improving approval boundaries, approver models, operation allowlists, and traceability in this repository.
---

# Ops Gate

Use this skill when the goal is to prevent unsafe agent operations, not merely to record them afterward.

## Start Here

1. Read `docs/ops-gate-workflow-and-boundaries.md`.
2. Read `docs/design.md`.
3. Read `docs/approval-policy.md`.
4. When touching gate boundaries or approval grading, read:
   - `skills/ops-gate/references/review-rules.md`
5. When touching backup behavior or rollback coverage, read:
   - `skills/ops-gate/references/backup-rules.md`
6. Inspect:
   - `devops_runner/plan.py`
   - `devops_runner/render.py`
   - `devops_runner/approvals/`
   - `devops_runner/backups.py`
   - `devops_runner/execution.py`
   - `devops_runner/audit.py`
   - `devops_runner/orchestrator.py`
7. Use these examples:
   - `plans/examples/smoke-test.json`
   - `plans/examples/web-auto-approval-test.json`
   - `tasks/01-local-baseline-audit/plans/01-capture-local-baseline.json`
   - `tasks/02-local-file-lifecycle/plans/01-create-and-delete-demo-file.json`

## Working Rules

- Treat “non-basic operation must enter the gate” as the primary product goal.
- Treat run history and `runner.jsonl` as the secondary goal.
- Prefer repo-relative paths in plans, docs, and demo tasks.
- Fill `operator` when the current manual approver is known.
- For medium/high/critical write steps, make backup scope explicit with `step.backup`.
- Do not claim that read-only semantics are machine-enforced unless the code path proves it.
- Keep approval semantics explicit: identify who the human approver is and where approval happens.
- Do not claim that backups automatically restore the system; rollback commands still need to be written.
- Preserve `runs/<task_id>/<run_id>/` and `backups/<task_id>/<run_id>/` as the current evidence boundary unless the user asks to redesign it.

## Expected Output

When using this skill, produce:

1. The current gate flow.
2. The current hard boundary vs soft convention boundary.
3. The gap between “approval system” and “full operation gate”.
4. The backup scope and rollback path for risky steps.
5. A concrete patch or split plan.
