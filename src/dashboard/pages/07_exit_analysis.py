import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics.exit_performance import ExitPerformanceAnalyzer
from src.dashboard.utils.db_connector import get_data_as_dataframe


def _parse_json(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return {}


st.title("📊 Exit Analysis")
st.caption("매도 성과 분석 및 파라미터 튜닝 제안")

col_filter1, col_filter2 = st.columns(2)
with col_filter1:
    lookback_days = st.slider("조회 기간 (일)", min_value=7, max_value=90, value=30, step=1)
with col_filter2:
    max_rows = st.slider("최대 조회 건수", min_value=100, max_value=2000, value=800, step=100)

since_ts = datetime.now(timezone.utc) - timedelta(days=lookback_days)

query = """
    SELECT
        COALESCE(executed_at, created_at) + interval '9 hours' AS sold_at,
        symbol,
        COALESCE(regime, 'UNKNOWN') AS regime,
        COALESCE(exit_reason, 'UNKNOWN') AS exit_reason,
        price,
        quantity,
        (signal_info->>'entry_avg_price')::numeric AS entry_avg_price,
        (post_exit_prices->'1h'->>'change_pct')::numeric AS post_1h_pct,
        (post_exit_prices->'4h'->>'change_pct')::numeric AS post_4h_pct,
        (post_exit_prices->'12h'->>'change_pct')::numeric AS post_12h_pct,
        (post_exit_prices->'24h'->>'change_pct')::numeric AS post_24h_pct,
        signal_info,
        post_exit_prices
    FROM trading_history
    WHERE side = 'SELL'
      AND status = 'FILLED'
      AND COALESCE(executed_at, created_at) >= :since_ts
    ORDER BY COALESCE(executed_at, created_at) DESC
    LIMIT :limit
"""

df = get_data_as_dataframe(query, {"since_ts": since_ts, "limit": max_rows})

if df.empty:
    st.info("선택한 기간에 SELL 체결 데이터가 없습니다.")
    st.stop()

# Numeric normalization
for col in [
    "price",
    "quantity",
    "entry_avg_price",
    "post_1h_pct",
    "post_4h_pct",
    "post_12h_pct",
    "post_24h_pct",
]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Fallback: entry_avg_price가 없는 경우 signal_info에서 재추출 시도
missing_entry = df["entry_avg_price"].isna()
if missing_entry.any():
    extracted = []
    for _, row in df[missing_entry].iterrows():
        info = _parse_json(row.get("signal_info"))
        try:
            extracted.append(float(info.get("entry_avg_price")))
        except Exception:
            extracted.append(np.nan)
    df.loc[missing_entry, "entry_avg_price"] = extracted

df["pnl_pct"] = np.where(
    (df["entry_avg_price"].notna()) & (df["entry_avg_price"] > 0),
    (df["price"] - df["entry_avg_price"]) / df["entry_avg_price"] * 100.0,
    np.nan,
)
df["notional_krw"] = df["price"] * df["quantity"]

total_sells = int(len(df))
pnl_sells = int(df["pnl_pct"].notna().sum())
post24_sells = int(df["post_24h_pct"].notna().sum())
avg_pnl = float(df["pnl_pct"].dropna().mean()) if pnl_sells > 0 else np.nan

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("SELL Count", f"{total_sells}")
with col_m2:
    st.metric("PnL Computable", f"{pnl_sells}")
with col_m3:
    st.metric("Post 24h Samples", f"{post24_sells}")
with col_m4:
    st.metric("Avg SELL PnL (%)", "N/A" if np.isnan(avg_pnl) else f"{avg_pnl:.2f}%")

st.markdown("---")

col_c1, col_c2 = st.columns(2)

with col_c1:
    st.markdown("#### Exit Reason별 PnL 분포")
    box_df = df[df["pnl_pct"].notna()].copy()
    if box_df.empty:
        st.info("PnL 계산 가능한 SELL 데이터가 없습니다.")
    else:
        fig_box = px.box(
            box_df,
            x="exit_reason",
            y="pnl_pct",
            color="exit_reason",
            points="all",
            title="PnL (%) Distribution by Exit Reason",
        )
        fig_box.update_layout(showlegend=False, xaxis_title="Exit Reason", yaxis_title="PnL (%)")
        st.plotly_chart(fig_box, use_container_width=True)

with col_c2:
    st.markdown("#### Post-Exit 시점별 평균 변화율")
    series = []
    for key, label in [
        ("post_1h_pct", "1h"),
        ("post_4h_pct", "4h"),
        ("post_12h_pct", "12h"),
        ("post_24h_pct", "24h"),
    ]:
        valid = df[key].dropna()
        series.append(
            {
                "window": label,
                "avg_change_pct": float(valid.mean()) if len(valid) > 0 else np.nan,
                "samples": int(len(valid)),
            }
        )
    line_df = pd.DataFrame(series)
    if line_df["samples"].sum() == 0:
        st.info("Post-exit 추적 데이터가 아직 부족합니다.")
    else:
        fig_line = px.line(
            line_df,
            x="window",
            y="avg_change_pct",
            markers=True,
            title="Average Change (%) after Exit",
        )
        fig_line.update_traces(text=line_df["samples"], textposition="top center")
        fig_line.update_layout(xaxis_title="Window", yaxis_title="Avg Change (%)")
        st.plotly_chart(fig_line, use_container_width=True)

st.markdown("#### Regime × Exit Reason 평균 PnL 히트맵")
heat_df = df[df["pnl_pct"].notna()].copy()
if heat_df.empty:
    st.info("히트맵을 생성할 PnL 데이터가 없습니다.")
else:
    pivot = (
        heat_df.groupby(["regime", "exit_reason"], as_index=False)["pnl_pct"]
        .mean()
        .pivot(index="regime", columns="exit_reason", values="pnl_pct")
    )
    fig_heat = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="RdYlGn",
            zmid=0,
            colorbar=dict(title="Avg PnL (%)"),
        )
    )
    fig_heat.update_layout(height=380)
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("---")
st.markdown("#### 파라미터 튜닝 제안 (룰 기반)")

by_exit_reason = {}
for reason, g in df.groupby("exit_reason"):
    by_exit_reason[reason] = {
        "avg_post_24h_pct": float(g["post_24h_pct"].dropna().mean()) if g["post_24h_pct"].notna().any() else None,
        "avg_post_4h_pct": float(g["post_4h_pct"].dropna().mean()) if g["post_4h_pct"].notna().any() else None,
    }

by_regime = {}
for regime, g in df.groupby("regime"):
    target = g[g["exit_reason"].isin(["TRAILING_STOP", "TAKE_PROFIT"])]
    if len(target) > 0:
        early_rate = float((target["post_24h_pct"] > 2.0).fillna(False).mean())
    else:
        early_rate = None
    by_regime[regime] = {"early_exit_rate": early_rate}

summary_for_suggestion = {
    "total_sells": int(len(df)),
    "by_exit_reason": by_exit_reason,
    "by_regime": by_regime,
}

suggestions = ExitPerformanceAnalyzer.generate_tuning_suggestions_from_summary(
    summary_for_suggestion,
    min_samples=20,
)

for idx, s in enumerate(suggestions, start=1):
    st.write(f"{idx}. {s}")

st.markdown("---")
st.markdown("#### 상세 데이터")

display_df = df[
    [
        "sold_at",
        "symbol",
        "regime",
        "exit_reason",
        "price",
        "quantity",
        "entry_avg_price",
        "pnl_pct",
        "post_1h_pct",
        "post_4h_pct",
        "post_12h_pct",
        "post_24h_pct",
    ]
].copy()

for col in ["price", "entry_avg_price"]:
    display_df[col] = pd.to_numeric(display_df[col], errors="coerce").map(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
display_df["quantity"] = pd.to_numeric(display_df["quantity"], errors="coerce").map(
    lambda x: f"{x:,.8f}" if pd.notna(x) else "N/A"
)
for col in ["pnl_pct", "post_1h_pct", "post_4h_pct", "post_12h_pct", "post_24h_pct"]:
    display_df[col] = pd.to_numeric(display_df[col], errors="coerce").map(
        lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
    )

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)
