import hashlib
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.common.db import get_db_session
from src.common.models import NewsArticle, NewsRiskScore, NewsSummary
from src.config.strategy import get_config

DEFAULT_RSS_SOURCES = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
]

SYMBOL_KEYWORDS = {
    "KRW-BTC": ["bitcoin", "btc", "비트코인"],
    "KRW-ETH": ["ethereum", "eth", "이더리움"],
    "KRW-XRP": ["xrp", "리플"],
    "KRW-SOL": ["solana", "sol", "솔라나"],
    "KRW-DOGE": ["dogecoin", "doge", "도지"],
}

HIGH_RISK_KEYWORDS = {
    "hack": 18,
    "exploit": 18,
    "breach": 16,
    "lawsuit": 14,
    "sec": 12,
    "ban": 14,
    "bankruptcy": 20,
    "liquidation": 12,
    "outage": 10,
    "suspend": 10,
    "probe": 8,
    "sanction": 10,
    "fraud": 16,
    "bearish": 8,
    "dump": 8,
    "crash": 12,
    "해킹": 18,
    "소송": 14,
    "규제": 12,
    "상장폐지": 16,
    "중단": 10,
    "파산": 20,
}

POSITIVE_KEYWORDS = {
    "approval": -8,
    "adoption": -6,
    "partnership": -5,
    "inflow": -4,
    "upgrade": -3,
    "etf": -4,
    "승인": -8,
    "채택": -6,
    "호재": -6,
    "상승": -4,
}

ISSUE_TOPICS = {
    "거시/정책": [
        "tariff",
        "inflation",
        "fed",
        "interest rate",
        "macro",
        "economy",
        "관세",
        "금리",
        "인플레이션",
        "거시",
        "경제",
        "정책",
    ],
    "규제/법률": [
        "regulation",
        "sec",
        "lawsuit",
        "court",
        "compliance",
        "법원",
        "규제",
        "소송",
        "제재",
        "당국",
    ],
    "거래소/보안": [
        "exchange",
        "hack",
        "exploit",
        "breach",
        "outage",
        "suspend",
        "거래소",
        "해킹",
        "보안",
        "중단",
        "점검",
    ],
    "기관/ETF": [
        "etf",
        "goldman",
        "blackrock",
        "franklin templeton",
        "fund",
        "institution",
        "기관",
        "자금",
        "유입",
        "운용사",
    ],
    "프로젝트/기술": [
        "upgrade",
        "mainnet",
        "fork",
        "partnership",
        "adoption",
        "네트워크",
        "업그레이드",
        "파트너십",
        "채택",
        "출시",
    ],
}


def get_rss_sources() -> List[str]:
    """환경변수 또는 기본값 기반 RSS 소스 목록을 반환합니다."""
    raw = os.getenv("NEWS_RSS_SOURCES", "").strip()
    if not raw:
        return DEFAULT_RSS_SOURCES

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or DEFAULT_RSS_SOURCES


def _normalize_space(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _strip_html(text: str) -> str:
    """RSS description/content에 섞인 HTML 태그를 최소한으로 제거합니다."""
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return _normalize_space(cleaned)


def _parse_datetime(raw: str) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)

    value = raw.strip()

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    iso_candidate = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _child_text(elem: ET.Element, names: Iterable[str]) -> str:
    targets = set(names)
    for child in list(elem):
        if _local_name(child.tag).lower() in targets:
            if child.text and child.text.strip():
                return child.text.strip()
    return ""


def _atom_link(entry: ET.Element) -> str:
    for child in list(entry):
        if _local_name(child.tag).lower() != "link":
            continue
        href = (child.attrib or {}).get("href")
        if href:
            return href.strip()
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def parse_feed_xml(xml_text: str, feed_url: str) -> List[Dict[str, Any]]:
    """
    RSS/Atom 피드를 공통 포맷으로 파싱합니다.

    반환 필드: title, link, content, published_at, feed_url, source
    """
    if not xml_text or not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: List[Dict[str, Any]] = []
    root_name = _local_name(root.tag).lower()
    source = feed_url.split("/")[2] if "//" in feed_url else feed_url

    if root_name == "rss":
        channel = root.find("channel")
        if channel is None:
            return []
        iterable = channel.findall("item")
        for item in iterable:
            title = _child_text(item, ["title"])
            link = _child_text(item, ["link"])
            description = _child_text(item, ["description", "content", "encoded"])
            published = _child_text(item, ["pubdate", "published", "updated", "dc:date"])

            if not title and not link:
                continue

            items.append(
                {
                    "source": source,
                    "feed_url": feed_url,
                    "title": _normalize_space(title),
                    "link": link,
                    "content": _strip_html(description),
                    "published_at": _parse_datetime(published),
                }
            )

    elif root_name == "feed":
        iterable = [child for child in list(root) if _local_name(child.tag).lower() == "entry"]
        for entry in iterable:
            title = _child_text(entry, ["title"])
            link = _atom_link(entry)
            summary = _child_text(entry, ["summary", "content"])
            published = _child_text(entry, ["published", "updated"])

            if not title and not link:
                continue

            items.append(
                {
                    "source": source,
                    "feed_url": feed_url,
                    "title": _normalize_space(title),
                    "link": link,
                    "content": _strip_html(summary),
                    "published_at": _parse_datetime(published),
                }
            )

    return items


def extract_symbols(title: str, content: str) -> List[str]:
    """뉴스 본문/제목에서 심볼 키워드를 추출합니다."""
    merged = f"{title or ''} {content or ''}".lower()
    matched: List[str] = []
    for symbol, keywords in SYMBOL_KEYWORDS.items():
        if any(keyword in merged for keyword in keywords):
            matched.append(symbol)

    # 심볼 힌트가 없더라도 전체 시장 이슈로 볼 수 있는 경우 BTC를 기본 축으로 둔다.
    if not matched and any(k in merged for k in ["crypto", "bitcoin", "market", "가상자산", "암호화폐"]):
        matched.append("KRW-BTC")

    return sorted(set(matched))


def score_article_risk(title: str, content: str) -> Dict[str, Any]:
    """
    기사 단위 위험 점수를 계산합니다.

    한국어 유지보수 주석:
    - 점수는 0~100 범위에서 clamp합니다.
    - 기본값 40은 '중립~약경계' 수준으로 설정했습니다.
    - 고위험 키워드는 가산, 긍정 키워드는 감산하여 단순하지만 예측 가능한 규칙을 유지합니다.
    """
    text = f"{title or ''} {content or ''}".lower()

    score = 40.0
    drivers: List[str] = []

    for keyword, weight in HIGH_RISK_KEYWORDS.items():
        if keyword in text:
            score += weight
            drivers.append(keyword)

    for keyword, weight in POSITIVE_KEYWORDS.items():
        if keyword in text:
            score += weight
            drivers.append(keyword)

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "drivers": sorted(set(drivers)),
    }


def _make_content_hash(title: str, link: str, content: str, published_at: datetime) -> str:
    payload = "|".join(
        [
            _normalize_space(title or ""),
            _normalize_space(link or ""),
            _normalize_space(content or "")[:500],
            published_at.isoformat(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _fetch_feed_xml(client: httpx.AsyncClient, feed_url: str) -> str:
    resp = await client.get(feed_url)
    resp.raise_for_status()
    return resp.text


async def news_ingest_rss_job() -> None:
    """RSS 피드에서 뉴스를 수집하여 DB에 적재합니다."""
    feeds = get_rss_sources()
    timeout_seconds = float(os.getenv("NEWS_RSS_TIMEOUT_SECONDS", "12"))

    inserted = 0
    skipped = 0
    failed = 0

    print(f"[Scheduler] RSS ingest started. feeds={len(feeds)}")

    async with get_db_session() as session:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            for feed_url in feeds:
                try:
                    xml_text = await _fetch_feed_xml(client, feed_url)
                    parsed_items = parse_feed_xml(xml_text, feed_url)
                except Exception as exc:
                    failed += 1
                    print(f"[Scheduler] RSS ingest failed for {feed_url}: {exc}")
                    continue

                for item in parsed_items[:200]:
                    title = item.get("title", "")
                    link = item.get("link", "")
                    content = item.get("content", "")
                    published_at = item.get("published_at") or datetime.now(timezone.utc)

                    symbols = extract_symbols(title, content)
                    risk = score_article_risk(title, content)
                    content_hash = _make_content_hash(title, link, content, published_at)

                    stmt = (
                        insert(NewsArticle)
                        .values(
                            source=item.get("source", "rss"),
                            feed_url=feed_url,
                            article_url=link or None,
                            title=title or "(untitled)",
                            content=content,
                            published_at=published_at,
                            symbols=symbols,
                            risk_signal_score=risk["score"],
                            risk_drivers=risk["drivers"],
                            content_hash=content_hash,
                            ingested_at=datetime.now(timezone.utc),
                        )
                        .on_conflict_do_nothing(index_elements=["content_hash"])
                    )
                    result = await session.execute(stmt)
                    if result.rowcount and result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1

    print(f"[Scheduler] RSS ingest done. inserted={inserted}, skipped={skipped}, failed_feeds={failed}")


def _risk_level(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _risk_level_korean(level: str) -> str:
    mapping = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"}
    return mapping.get(level, "보통")


def _extract_issue_topics(title: str, content: str) -> List[str]:
    merged = f"{title or ''} {content or ''}".lower()
    matched: List[str] = []
    for topic, keywords in ISSUE_TOPICS.items():
        if any(keyword in merged for keyword in keywords):
            matched.append(topic)
    return matched


def _driver_label(driver: str) -> str:
    d = (driver or "").lower()
    if d in {"hack", "exploit", "breach", "해킹"}:
        return "보안 사고"
    if d in {"lawsuit", "court", "sec", "규제", "소송"}:
        return "규제/법률 리스크"
    if d in {"liquidation", "dump", "crash", "파산"}:
        return "급락/청산 압력"
    if d in {"outage", "suspend", "중단"}:
        return "거래소 운영 이슈"
    if d in {"approval", "adoption", "partnership", "etf", "승인", "채택"}:
        return "제도권/채택 이슈"
    return driver


def _build_summary(symbol: str, articles: List[NewsArticle], risk_score: float) -> Dict[str, Any]:
    level = _risk_level(risk_score)
    level_ko = _risk_level_korean(level)

    driver_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    for article in articles:
        drivers = article.risk_drivers or []
        for driver in drivers:
            driver_counter[_driver_label(str(driver))] += 1

        for topic in _extract_issue_topics(article.title or "", article.content or ""):
            topic_counter[topic] += 1

    if topic_counter:
        top_topics = [name for name, _ in topic_counter.most_common(3)]
    else:
        top_topics = ["시장 일반 동향"]

    top_drivers = [k for k, _ in driver_counter.most_common(5)]
    topic_points = [f"{name} 이슈 {cnt}건" for name, cnt in topic_counter.most_common(3)]
    if not topic_points:
        topic_points = ["주요 이슈 카테고리 데이터 부족"]

    summary_text = (
        f"최근 {len(articles)}건 기사 분석 결과 {symbol} 뉴스 리스크는 {level_ko}({risk_score:.1f}) 수준입니다. "
        f"핵심 이슈는 {', '.join(top_topics)} 중심입니다."
    )
    if top_drivers:
        summary_text += f" 위험 신호는 {', '.join(top_drivers[:3])}가 반복 관측됩니다."

    return {
        "summary_text": summary_text,
        "key_points": topic_points,
        "drivers": top_drivers,
        "risk_level": level,
    }


async def news_summarize_and_score_job() -> None:
    """최근 뉴스 데이터를 심볼 단위로 요약하고 위험 점수를 집계합니다."""
    window_hours = int(os.getenv("NEWS_RISK_WINDOW_HOURS", "6"))
    max_articles = int(os.getenv("NEWS_MAX_ARTICLES_PER_SYMBOL", "80"))

    now = datetime.now(timezone.utc)
    window_end = now.replace(minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=window_hours)

    symbols = get_config().SYMBOLS

    print(
        "[Scheduler] RSS summarize started. "
        f"symbols={len(symbols)}, window={window_start.isoformat()}~{window_end.isoformat()}"
    )

    async with get_db_session() as session:
        for symbol in symbols:
            stmt = (
                select(NewsArticle)
                .where(NewsArticle.published_at >= window_start)
                .where(NewsArticle.published_at < window_end)
                .where(NewsArticle.symbols.any(symbol))
                .order_by(NewsArticle.published_at.desc())
                .limit(max_articles)
            )
            rows = (await session.execute(stmt)).scalars().all()

            if not rows:
                summary_text = (
                    f"최근 {window_hours}시간 내 {symbol} 관련 RSS 뉴스가 충분하지 않아 "
                    "리스크 판단 신뢰도가 낮습니다."
                )
                risk_score = 0.0
                drivers = ["insufficient_data"]
                level = "LOW"
                key_points = ["수집된 관련 뉴스 부족"]
                article_count = 0
            else:
                # 한국어 유지보수 주석:
                # - 최신 기사일수록 시장 반응에 미치는 영향이 크다고 가정해 선형 가중치 적용
                # - 최근 순서가 이미 정렬되어 있으므로 인덱스 기반으로 가중치를 부여합니다.
                weights = [max(0.2, 1.0 - idx * 0.05) for idx in range(len(rows))]
                weighted_scores = [float(r.risk_signal_score or 0.0) * w for r, w in zip(rows, weights)]
                risk_score = sum(weighted_scores) / sum(weights)

                summary_bundle = _build_summary(symbol, rows, risk_score)
                summary_text = summary_bundle["summary_text"]
                key_points = summary_bundle["key_points"]
                drivers = summary_bundle["drivers"]
                level = summary_bundle["risk_level"]
                article_count = len(rows)

            summary_stmt = (
                insert(NewsSummary)
                .values(
                    symbol=symbol,
                    window_start=window_start,
                    window_end=window_end,
                    summary_text=summary_text,
                    key_points=key_points,
                    article_count=article_count,
                    model_used="rss-rule-v1",
                )
                .on_conflict_do_update(
                    index_elements=["symbol", "window_start", "window_end"],
                    set_={
                        "summary_text": summary_text,
                        "key_points": key_points,
                        "article_count": article_count,
                        "model_used": "rss-rule-v1",
                        "created_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(summary_stmt)

            risk_stmt = (
                insert(NewsRiskScore)
                .values(
                    symbol=symbol,
                    window_start=window_start,
                    window_end=window_end,
                    risk_score=round(float(risk_score), 2),
                    risk_level=level,
                    drivers=drivers,
                )
                .on_conflict_do_update(
                    index_elements=["symbol", "window_start", "window_end"],
                    set_={
                        "risk_score": round(float(risk_score), 2),
                        "risk_level": level,
                        "drivers": drivers,
                        "created_at": datetime.now(timezone.utc),
                    },
                )
            )
            await session.execute(risk_stmt)

    print("[Scheduler] RSS summarize done.")
