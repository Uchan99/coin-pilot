CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    feed_url TEXT NOT NULL,
    article_url TEXT,
    title TEXT NOT NULL,
    content TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    risk_signal_score NUMERIC(6, 2) NOT NULL DEFAULT 0,
    risk_drivers JSONB,
    content_hash VARCHAR(64) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_news_articles_content_hash UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS idx_news_articles_published_at
ON news_articles (published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_articles_symbols_gin
ON news_articles USING GIN (symbols);

CREATE TABLE IF NOT EXISTS news_summaries (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    summary_text TEXT NOT NULL,
    key_points JSONB,
    article_count INTEGER NOT NULL DEFAULT 0,
    model_used VARCHAR(50) NOT NULL DEFAULT 'rss-rule-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_news_summaries_symbol_window UNIQUE (symbol, window_start, window_end)
);

CREATE INDEX IF NOT EXISTS idx_news_summaries_symbol_window
ON news_summaries (symbol, window_end DESC);

CREATE TABLE IF NOT EXISTS news_risk_scores (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    risk_score NUMERIC(6, 2) NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    drivers JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_news_risk_scores_symbol_window UNIQUE (symbol, window_start, window_end)
);

CREATE INDEX IF NOT EXISTS idx_news_risk_scores_symbol_window
ON news_risk_scores (symbol, window_end DESC);
