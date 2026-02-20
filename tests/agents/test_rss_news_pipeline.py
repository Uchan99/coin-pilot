from types import SimpleNamespace

from src.agents.news.rss_news_pipeline import (
    _build_summary,
    extract_symbols,
    parse_feed_xml,
    score_article_risk,
)


def test_extract_symbols_from_korean_and_english_text():
    symbols = extract_symbols(
        "Bitcoin ETF approval could impact Ethereum too",
        "비트코인과 이더리움 동반 상승 가능성",
    )
    assert "KRW-BTC" in symbols
    assert "KRW-ETH" in symbols


def test_score_article_risk_high_case():
    result = score_article_risk(
        "Major exchange hack triggers liquidation risk",
        "Regulators probe potential fraud after security breach",
    )
    assert result["score"] >= 70
    assert "hack" in result["drivers"] or "breach" in result["drivers"]


def test_score_article_risk_positive_case():
    result = score_article_risk(
        "ETF approval and adoption boosts sentiment",
        "Partnership news points to broader inflow",
    )
    assert result["score"] <= 40


def test_parse_feed_xml_rss_items():
    xml = """
    <rss version="2.0">
      <channel>
        <title>Sample Feed</title>
        <item>
          <title>BTC market update</title>
          <link>https://example.com/a</link>
          <description>Bitcoin moved higher.</description>
          <pubDate>Fri, 20 Feb 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    items = parse_feed_xml(xml, "https://example.com/rss")
    assert len(items) == 1
    assert items[0]["title"] == "BTC market update"
    assert items[0]["link"] == "https://example.com/a"


def test_parse_feed_xml_atom_items():
    xml = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Atom Feed</title>
      <entry>
        <title>ETH outlook</title>
        <link href="https://example.com/b" />
        <summary>Ethereum momentum remains stable.</summary>
        <updated>2026-02-20T10:00:00Z</updated>
      </entry>
    </feed>
    """
    items = parse_feed_xml(xml, "https://example.com/atom")
    assert len(items) == 1
    assert items[0]["title"] == "ETH outlook"
    assert items[0]["link"] == "https://example.com/b"


def test_build_summary_is_korean_issue_focused():
    articles = [
        SimpleNamespace(
            title="Bitcoin pops then drops as Supreme Court strikes down tariffs",
            content="macro policy and tariff news shook the crypto market",
            risk_drivers=["sec", "tariff"],
        ),
        SimpleNamespace(
            title="ETF flows and institutional adoption continue",
            content="ETF inflow trend remains stable",
            risk_drivers=["etf", "approval"],
        ),
    ]

    summary = _build_summary("KRW-BTC", articles, risk_score=39.1)

    assert "핵심 이슈는" in summary["summary_text"]
    assert "Bitcoin pops then drops" not in summary["summary_text"]
    assert any("이슈" in point for point in summary["key_points"])
