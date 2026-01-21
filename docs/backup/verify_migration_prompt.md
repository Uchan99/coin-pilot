# Prompt for Claude Code Verification (Migration Config)

Claude Code에게 아래 내용을 복사해서 전달하여, 현재 마이그레이션 준비 상태를 최종 검증받으세요.

---

**[프롬프트 시작]**

@Codebase
안녕하세요 Claude Code, 우리는 현재 **CoinPilot v3.0** 프로젝트의 Week 1 개발(DB 스키마 및 프로젝트 구조)을 마치고, 개발 환경을 **VMware(Linux)**에서 **WSL2(Windows)**로 이전(Migration)하려 합니다.

현재 Antigravity(IDE)가 작성한 마이그레이션 가이드와 백업 파일들이 적절한지 **Cross-Check**를 부탁드립니다.

### 1. 리뷰 대상 파일
- **가이드**: `docs/backup/migration_guide.md` (WSL2 설정 및 설치 절차)
- **맥락 문서**: `docs/backup/migration_context.md` (프로젝트 상태 요약)
- **복원 프롬프트**: `docs/backup/restore_prompt.md`
- **결과 보고서**: `docs/work-result/week1-walkthrough.md`

### 2. 사용자 하드웨어 스펙
- **CPU**: Intel Core i5-12400F (6 Performance Cores / 12 Threads)
- **RAM**: 32GB
- **GPU**: NVIDIA GeForce RTX 3060 Ti (8GB)
- **OS**: Windows 11 (예상)

### 3. 중점 검증 요청 사항
1.  **리소스 할당 적절성 (`.wslconfig`)**:
    - 현재 가이드(`migration_guide.md`)는 **Memory 16GB, Processors 8개**를 할당하도록 제안했습니다.
    - 사용자는 "개발 환경을 켜두고 고사양 게임도 병행"하는 패턴을 가지고 있습니다. 이 설정이 윈도우와 WSL2 간의 **밸런스**를 잘 맞춘 것인지 객관적으로 평가해주세요.
2.  **마이그레이션 절차의 빈틈**:
    - `git clone` 후 `.env` 설정, `docker compose up`, `python venv` 설정 등 필수 절차 중 누락된 것이 없는지 확인해주세요.
    - 특히 Windows와 WSL2 간의 파일 시스템 접근이나 권한 문제 등 잠재적 리스크가 있다면 알려주세요.
3.  **데이터 보존**:
    - 현재 DB 데이터는 백업하지 않고 "새 환경에서 다시 수집(Backfill)하거나 테스트"하는 방향으로 잡았습니다. Week 1 단계에서 이 전략이 타당한지 확인해주세요.

위 내용을 검토하고, 수정이 필요한 부분이 있다면 구체적인 `.wslconfig` 값이나 절차를 제안해주세요.

**[프롬프트 끝]**
