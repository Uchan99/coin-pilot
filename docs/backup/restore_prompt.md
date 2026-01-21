# Context Restoration Prompt

새로운 환경(WSL2)에서 Antigravity(또는 Claude Code)를 처음 실행할 때, 아래 프롬프트를 입력하여 이전 작업의 맥락을 완벽하게 이어가세요.

---

**프롬프트 복사/붙여넣기:**

```text
안녕! 나는 개발 환경을 기존 VMware(Linux)에서 WSL2로 막 이전했어.
프로젝트의 연속성을 위해 현재 상태를 파악해줘.

1. `docs/backup/migration_context.md` 파일을 정독해서 프로젝트 목표, Week 1 완료 내역, 그리고 내가 중요하게 생각하는 원칙(User Rules)을 복원해줘.
2. `docs/memory/activeContext.md`와 `systemPatterns.md`를 읽고 기술 스택과 현재 구현된 아키텍처를 숙지해줘.
3. 모든 파악이 끝나면 "Week 2 개발 준비 완료"라고 알려주고, Rule Engine 구현을 위한 계획 수립 단계로 넘어가자.
```
