from src.agents.sql_agent import build_readonly_db_url, contains_blocked_sql


def test_contains_blocked_sql_for_dml():
    assert contains_blocked_sql("DELETE FROM trading_history") is True
    assert contains_blocked_sql("with t as (select 1) update x set a=1") is True


def test_contains_blocked_sql_for_select_only():
    assert contains_blocked_sql("SELECT * FROM market_data LIMIT 10") is False


def test_build_readonly_db_url_appends_option():
    base = "postgresql+psycopg2://u:p@localhost:5432/dbname"
    built = build_readonly_db_url(base)
    assert "default_transaction_read_only%3Don" in built


def test_build_readonly_db_url_preserves_existing_query_params():
    base = "postgresql+psycopg2://u:p@localhost:5432/dbname?sslmode=require"
    built = build_readonly_db_url(base)
    assert "sslmode=require" in built
    assert "default_transaction_read_only%3Don" in built
