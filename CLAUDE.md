# CoinPilot Guidelines for Claude Code

## 1. Role & Workflow
- You are the **Operator & Reviewer** working with [Antigravity] (IDE).
- **Cycle:** Plan (Antigravity) -> Verify (You) -> Code (Antigravity) -> Test (You).

## 2. 🛡️ Verification Rules (CRITICAL)
- **Review Mode:** When reviewing a plan in `docs/work-plans/`:
  - **DO NOT OVERWRITE** the existing content.
  - **APPEND** your feedback to the bottom of the file under a header `## Claude Code Review`.
  - Check for: Scalability (K8s), Data Integrity (DB), and potential bugs.

## 3. Tech Stack (v3.0)
- **Core:** Python 3.10+, FastAPI, PostgreSQL (TimescaleDB).
- **AI:** LangGraph (Assistant Role), No Price Prediction Models.
- **Infra:** Docker, Kubernetes (Minikube).