# docs/AGENTS.md

## Document creation rule
- Always start from templates in docs/templates/.
  - work-plan.template.md / work-result.template.md / troubleshooting.template.md
- Naming (preferred; keep legacy files as-is):
  - work-plans: <NN>_<topic>_plan.md
  - work-result: <NN>_<topic>_result.md
  - troubleshooting: <NN>_<topic>.md

## Required headers (recommended for consistency)
- Plan: 작성일 / 상태 / 우선순위 / 관련 문서(Plan→Charter 필수)
- Result: 작성일 / 작성자 / 관련 계획서 / 상태 / 완료 범위(Phase) / 선반영 여부
- Troubleshooting: 작성일 / 상태 / 우선순위 / 관련 문서 / Charter update 필요 여부

## Traceability (required)
- Result MUST link to its Plan.
- Troubleshooting MUST link to the relevant Plan/Result.
- If plan/result were updated due to an incident, add the troubleshooting link and summarize what changed.

## Writing style
- Objective, reproducible, ops-friendly.
- Include (as applicable): 목적/범위/검증/롤백/운영 체크리스트.
- If a file name doesn't match the actual completion scope (e.g., phase1 in name but phase2/3 done),
  keep the filename but record truth in header fields (Status / Completion Range / Extra implemented).

## Architecture decision record (required in Plan/Result)
- Plan must include:
  - alternatives (>= 3 when reasonable)
  - selected approach
  - benefits/tradeoffs + mitigation
- Result must include:
  - what actually worked in practice (observed benefits/downsides)
  - what changed vs plan (and why)

## Korean code comments policy (required for non-trivial logic)
- Prefer Korean comments that explain intent + rationale + invariants + edge cases + failure modes.
- Comment “why” more than “what”. Use docstrings for public functions/classes and inline comments for tricky sections.
- If logic is complex: add a short “요약 주석” at the top of the block explaining the strategy.

## Research hygiene
- Prefer primary sources: official docs/specs/release notes.
- Avoid low-quality SEO pages; sanity-check freshness and credibility.
- Add a “References” section with links in plan/result/troubleshooting when research was used.

## “Lightweight doc” mode (allowed)
- For small changes, it’s OK to omit empty sections and keep only:
  - Plan: scope + phases + verify + rollback + files (+ decision summary)
  - Result: changes + verify + ops checklist (+ decision review)
  - Troubleshooting: only when incidents/issues occur
- Even in lightweight mode, never omit: 변경 요약 / 검증 / 롤백(or 안전장치) / 관련 문서 링크