# AGENTS.md (repo root)

## Source of truth
- Start every task by reading: docs/PROJECT_CHARTER.md
- If implementation/monitoring requires changing rules/scope/ops policy, update PROJECT_CHARTER.md and append to its changelog.
- Never change core definitions silently (metrics, risk rules, thresholds, naming, workflow). Always document.

## Required workflow (documents are mandatory)
1) Before coding, write a plan:
   - Independent work: docs/work-plans/<NN>_<topic>_plan.md
   - Epic subtask: docs/work-plans/<EPIC>-<subNN>_<topic>_plan.md
   - (legacy allowed) weekN_<topic>.md
2) After writing the plan, get explicit user confirmation/approval.
   - Mark plan status as `Approval Pending` until approved.
   - Do not implement/deploy/migrate before approval, except emergency mitigation.
   - If emergency mitigation was needed, record reason and post-approval trace in the plan/result.
3) Implement following the approved plan.
   - If the plan changes, update the plan and add a change-log entry in that plan.
4) After coding, write a result report:
   - Independent work: docs/work-result/<NN>_<topic>_result.md
   - Epic subtask: docs/work-result/<EPIC>-<subNN>_<topic>_result.md
   - If phased, append Phase 2+ at the bottom of the same result file.
5) If issues arise (monitoring/bug/ops):
   - Independent work: docs/troubleshooting/<NN>_<topic>.md
   - Epic subtask: docs/troubleshooting/<EPIC>-<subNN>_<topic>.md
   - Link it from the related plan/result, and record any charter updates.

## Numbering policy (required)
- Keep independent streams on top-level numeric IDs (`18_`, `29_`, ...).
- When work is a subtask of an existing epic, keep the epic prefix (`17-01_`, `17-02_`, ...).
- Do not create a new top-level number for work that is clearly part of an existing epic.

## Traceability (required)
- Plan/Result/Troubleshooting must reference each other when applicable:
  - Result must link to its Plan.
  - Troubleshooting must link to the relevant Plan/Result.
  - Plan should link back to Troubleshooting if the plan was created from an incident.
- Use templates in docs/templates/ when creating new docs.

## Engineering constraints (project stack)
- Python 3.10+, FastAPI (async), PostgreSQL + TimescaleDB, Redis, LangGraph/LangChain, (quant) GARCH.
- Favor small, verifiable changes. Add/adjust tests where meaningful.
- Include explicit “How to verify” commands (and expected checks) in the result doc.
- Follow existing repo conventions first (lint/test/format commands). If unknown, inspect pyproject.toml/Makefile/scripts and use what exists.

## Architecture & code clarity (required)
- When implementing, explicitly document:
  1) Why this architecture/design was chosen
  2) What alternatives were considered (>= 3 when reasonable)
  3) Advantages/tradeoffs vs alternatives
- Write detailed Korean comments for non-trivial logic so a new maintainer can understand quickly:
  - intent/why, invariants, edge cases, failure modes, tradeoffs (not just what the code does)

## Research & uncertainty
- If uncertain, research using reliable & recent sources (prefer primary sources) and record key references in docs.
- Maintain an objective tone (9–10). Explicitly list assumptions, unknowns, and risks rather than hand-waving.
