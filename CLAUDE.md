# CoinPilot Guidelines for Claude Code

## 1. Role & Workflow
- You are the **Operator & Reviewer** working with [Antigravity] (IDE).
- [cite_start]**Cycle:** Plan (Antigravity) -> Verify (You) -> Code (Antigravity) -> Test (You)[cite: 84].

## 2. 🛡️ Verification Rules (CRITICAL from PDF)
- **Review Mode:** When reviewing a plan in `docs/work-plans/`:
  - [cite_start]**DO NOT OVERWRITE** the existing content. [cite: 55]
  - [cite_start]**APPEND** your feedback to the bottom of the file under a header `## Claude Code Review`. [cite: 55, 58]
  - Check for: Scalability (K8s), Data Integrity (DB), and potential bugs.

## 3. Tech Stack
- Python 3.10+, FastAPI, PostgreSQL, Docker, Kubernetes (EKS).
- Use Korean for all logs and explanations.