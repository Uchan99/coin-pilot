#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.ai_decision_rag import build_ai_decision_rag_context
from src.agents.ai_decision_replay import AnalystReplaySample, load_recent_analyst_replay_samples
from src.agents.analyst import market_analyst_node
from src.agents.factory import get_primary_ai_decision_route


def _serialize_dt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _safe_median(values: List[float]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return round(float(median(cleaned)), 4)


def _safe_average(values: List[float]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return round(sum(cleaned) / len(cleaned), 4)


async def _run_single_analyst(
    sample: AnalystReplaySample,
    *,
    rag_context: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    동일 입력을 Analyst에 1회 실행한다.

    왜 Guardian을 제외하는가:
    - Phase 1의 목적은 "전략/사례 RAG가 Analyst 판단에 미치는 영향"을 가장 작게 분리해 보는 것이다.
    - Guardian까지 함께 실행하면 리스크 판단/프롬프트 차이까지 섞여 원인 분리가 어려워진다.
    """
    route = get_primary_ai_decision_route()
    state = {
        "messages": [],
        "symbol": sample.symbol,
        "strategy_name": sample.strategy_name,
        "market_context": sample.market_context,
        "indicators": sample.indicators,
        "llm_route": route,
        "rag_context": rag_context,
        "replay_mode": True,
        "analyst_decision": None,
        "guardian_decision": None,
        "final_decision": "REJECT",
        "final_reasoning": "offline replay",
    }
    result = await market_analyst_node(state)
    return result.get("analyst_decision", {})


def _build_record(
    sample: AnalystReplaySample,
    baseline: Dict[str, Any],
    rag_on: Dict[str, Any],
    rag_context: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_conf = baseline.get("confidence")
    rag_conf = rag_on.get("confidence")
    confidence_delta = None
    if isinstance(baseline_conf, int) and isinstance(rag_conf, int):
        confidence_delta = rag_conf - baseline_conf

    return {
        "sample_id": sample.sample_id,
        "created_at": sample.created_at.isoformat(),
        "symbol": sample.symbol,
        "strategy_name": sample.strategy_name,
        "regime": sample.regime,
        "baseline": {
            "decision": baseline.get("decision"),
            "confidence": baseline_conf,
            "reasoning": baseline.get("reasoning"),
            "latency_ms": baseline.get("latency_ms"),
            "estimated_cost_usd": baseline.get("estimated_cost_usd"),
            "usage": baseline.get("usage"),
        },
        "rag_on": {
            "decision": rag_on.get("decision"),
            "confidence": rag_conf,
            "reasoning": rag_on.get("reasoning"),
            "latency_ms": rag_on.get("latency_ms"),
            "estimated_cost_usd": rag_on.get("estimated_cost_usd"),
            "usage": rag_on.get("usage"),
            "rag_source_summary": rag_on.get("rag_source_summary", []),
        },
        "rag_context_preview": (rag_context.get("text") or "")[:500],
        "decision_changed": baseline.get("decision") != rag_on.get("decision"),
        "confidence_delta": confidence_delta,
        "baseline_parse_fail": str(baseline.get("reasoning") or "").startswith("분석가 출력 검증 실패:"),
        "rag_parse_fail": str(rag_on.get("reasoning") or "").startswith("분석가 출력 검증 실패:"),
    }


def _summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    baseline_latencies = [record["baseline"].get("latency_ms") for record in records]
    rag_latencies = [record["rag_on"].get("latency_ms") for record in records]
    baseline_costs = [record["baseline"].get("estimated_cost_usd") for record in records]
    rag_costs = [record["rag_on"].get("estimated_cost_usd") for record in records]
    confidence_deltas = [record.get("confidence_delta") for record in records if record.get("confidence_delta") is not None]

    return {
        "samples": len(records),
        "decision_changed_count": sum(1 for record in records if record["decision_changed"]),
        "baseline_parse_fail_count": sum(1 for record in records if record["baseline_parse_fail"]),
        "rag_parse_fail_count": sum(1 for record in records if record["rag_parse_fail"]),
        "baseline_latency_p50_ms": _safe_median(baseline_latencies),
        "rag_latency_p50_ms": _safe_median(rag_latencies),
        "baseline_avg_cost_usd": _safe_average(baseline_costs),
        "rag_avg_cost_usd": _safe_average(rag_costs),
        "avg_confidence_delta": _safe_average(confidence_deltas),
    }


async def _main(args: argparse.Namespace) -> int:
    samples = await load_recent_analyst_replay_samples(hours=args.hours, limit=args.limit)

    records: List[Dict[str, Any]] = []
    for sample in samples:
        rag_context = await build_ai_decision_rag_context(
            symbol=sample.symbol,
            regime=sample.regime,
            strategy_name=sample.strategy_name,
            lookback_days=args.case_lookback_days,
        )
        baseline = await _run_single_analyst(sample, rag_context=None)
        rag_on = await _run_single_analyst(sample, rag_context=rag_context)
        records.append(_build_record(sample, baseline, rag_on, rag_context))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": args.hours,
        "limit": args.limit,
        "case_lookback_days": args.case_lookback_days,
        "summary": _summarize(records),
        "records": records,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_serialize_dt),
            encoding="utf-8",
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_serialize_dt))
    return 0 if records else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="최근 BUY signal_info를 replay해 baseline Analyst와 RAG-on Analyst를 비교합니다."
    )
    parser.add_argument("--hours", type=int, default=168, help="최근 몇 시간의 BUY signal을 replay 대상으로 볼지")
    parser.add_argument("--limit", type=int, default=50, help="최대 replay 샘플 수")
    parser.add_argument("--case-lookback-days", type=int, default=30, help="과거 사례 RAG 조회 기간(일)")
    parser.add_argument("--output", type=str, default="", help="결과 JSON 파일 경로")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(parse_args())))
