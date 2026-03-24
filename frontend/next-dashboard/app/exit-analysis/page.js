"use client";
import { useState, useEffect, useCallback } from "react";
import PlotlyChart from "@/components/plotly-chart";
import { getExitAnalysis } from "@/lib/bot-api";

/*
 * Exit Analysis 페이지 — Stitch 디자인
 * Phase 3: /api/mobile/exit-analysis 실데이터 연동
 * KPI 4카드 + 박스플롯 + Post-Exit 라인 + 히트맵 + 상세 테이블
 * 기간(7~90일)/건수(100~2000) 필터 지원 — Streamlit과 동일 기능
 */

export default function ExitAnalysisPage() {
  const [days, setDays] = useState(30);
  const [limit, setLimit] = useState(800);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const result = await getExitAnalysis({ days, limit });
    setData(result);
    setLoading(false);
  }, [days, limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const kpi = data?.kpi || {};
  const postExit = data?.post_exit_avg || {};
  const heatmap = data?.heatmap || [];
  const sells = data?.sells || [];

  // 박스플롯: exit_reason별 pnl_pct 그룹핑
  const exitReasons = [...new Set(sells.map((s) => s.exit_reason).filter(Boolean))];
  const boxData = exitReasons.map((reason) => ({
    y: sells.filter((s) => s.exit_reason === reason && s.pnl_pct != null).map((s) => s.pnl_pct),
    name: reason,
    type: "box",
    boxpoints: "all",
    jitter: 0.3,
    pointpos: -1.8,
    marker: { size: 3 },
  }));

  // Post-exit 라인
  const windows = ["1h", "4h", "12h", "24h"];
  const avgChanges = windows.map((w) => postExit[w]?.avg_change_pct ?? null);
  const samples = windows.map((w) => postExit[w]?.samples ?? 0);

  // 히트맵 구성
  const regimes = [...new Set(heatmap.map((h) => h.regime))];
  const heatReasons = [...new Set(heatmap.map((h) => h.exit_reason))];
  const heatmapZ = regimes.map((regime) =>
    heatReasons.map((reason) => {
      const match = heatmap.find((h) => h.regime === regime && h.exit_reason === reason);
      return match ? match.avg_pnl_pct : null;
    })
  );

  return (
    <div className="space-y-6">
      {/* 필터 컨트롤 */}
      <div className="flex items-center gap-6 flex-wrap bg-surface-container rounded-xl border border-outline-variant/10 p-4">
        <div className="flex items-center gap-3">
          <label className="text-xs text-on-surface-variant font-bold uppercase">조회 기간</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-surface-low text-on-surface text-sm rounded-lg px-3 py-1.5 border border-outline-variant/20"
          >
            {[7, 14, 30, 60, 90].map((d) => (
              <option key={d} value={d}>{d}일</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-on-surface-variant font-bold uppercase">최대 건수</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-surface-low text-on-surface text-sm rounded-lg px-3 py-1.5 border border-outline-variant/20"
          >
            {[100, 200, 500, 800, 1000, 2000].map((n) => (
              <option key={n} value={n}>{n}건</option>
            ))}
          </select>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {loading && <span className="text-xs text-primary animate-pulse">Loading...</span>}
          <span className="text-[10px] text-on-surface-variant">SELL {sells.length}건 조회됨</span>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Sell Count", value: kpi.total_sells ?? 0, sub: `최근 ${days}일`, icon: "sell" },
          { label: "PnL Computable", value: kpi.pnl_computable ?? 0, sub: "Entry 데이터 있음", icon: "calculate" },
          { label: "Post 24h Samples", value: kpi.post_24h_samples ?? 0, sub: "24시간 추적 완료", icon: "schedule" },
          {
            label: "Avg Sell PnL (%)",
            value: kpi.avg_pnl_pct != null ? `${kpi.avg_pnl_pct >= 0 ? "+" : ""}${kpi.avg_pnl_pct.toFixed(2)}%` : "N/A",
            sub: "평균 실현 손익",
            icon: "trending_up",
            positive: kpi.avg_pnl_pct != null ? kpi.avg_pnl_pct >= 0 : null,
          },
        ].map(({ label, value, sub, icon, positive }) => (
          <div key={label} className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">{label}</span>
              <span className="material-symbols-outlined text-primary/40 text-lg">{icon}</span>
            </div>
            <div className={`text-2xl font-bold tracking-tight ${positive === true ? "text-tertiary" : positive === false ? "text-error" : "text-on-surface"}`}>
              {value}
            </div>
            <div className="text-xs text-on-surface-variant mt-1">{sub}</div>
          </div>
        ))}
      </div>

      {sells.length === 0 && !loading ? (
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-12 text-center text-on-surface-variant">
          선택한 기간에 SELL 체결 데이터가 없습니다.
        </div>
      ) : (
        <>
          {/* 차트 2열 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 박스플롯 */}
            <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
              <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2 px-2">
                PnL Distribution by Exit Reason
              </h4>
              {boxData.length > 0 ? (
                <PlotlyChart
                  data={boxData}
                  layout={{
                    height: 350,
                    showlegend: false,
                    yaxis: { title: "PnL (%)", gridcolor: "#1f2a3d", zeroline: true, zerolinecolor: "#424754" },
                    xaxis: { gridcolor: "#1f2a3d" },
                    margin: { l: 50, r: 20, t: 10, b: 60 },
                  }}
                />
              ) : (
                <div className="h-[350px] flex items-center justify-center text-on-surface-variant text-sm">PnL 데이터 없음</div>
              )}
            </div>

            {/* Post-exit 라인 */}
            <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
              <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2 px-2">
                Post-Exit Opportunity Analysis
              </h4>
              <PlotlyChart
                data={[{
                  x: windows,
                  y: avgChanges,
                  type: "scatter",
                  mode: "lines+markers+text",
                  text: avgChanges.map((v) => v != null ? `${v > 0 ? "+" : ""}${v.toFixed(2)}%` : "N/A"),
                  textposition: "top center",
                  textfont: { color: "#c2c6d6", size: 10 },
                  line: { color: "#4ae176", width: 2 },
                  marker: { color: "#4ae176", size: 8 },
                  customdata: samples,
                  hovertemplate: "%{x}: %{y:.2f}% (n=%{customdata})<extra></extra>",
                }]}
                layout={{
                  height: 350,
                  yaxis: { title: "Avg Change (%)", gridcolor: "#1f2a3d", zeroline: true, zerolinecolor: "#424754" },
                  xaxis: { title: "Window", gridcolor: "#1f2a3d" },
                  margin: { l: 50, r: 20, t: 10, b: 50 },
                }}
              />
            </div>
          </div>

          {/* 히트맵 */}
          {heatmap.length > 0 && (
            <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
              <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2 px-2">
                Regime × Exit Performance Matrix
              </h4>
              <PlotlyChart
                data={[{
                  z: heatmapZ,
                  x: heatReasons,
                  y: regimes,
                  type: "heatmap",
                  colorscale: [
                    [0, "#93000a"],
                    [0.5, "#2a3548"],
                    [1, "#00a74b"],
                  ],
                  zmid: 0,
                  text: heatmapZ.map((row) => row.map((v) => v != null ? `${v > 0 ? "+" : ""}${v.toFixed(2)}%` : "")),
                  texttemplate: "%{text}",
                  textfont: { color: "#d7e3fc", size: 11 },
                  showscale: false,
                }]}
                layout={{
                  height: 280,
                  margin: { l: 80, r: 20, t: 10, b: 60 },
                  xaxis: { tickangle: -30 },
                }}
              />
            </div>
          )}

          {/* 상세 테이블 */}
          <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
            <div className="px-6 py-4 border-b border-outline-variant/10">
              <h3 className="font-bold">Exit Execution Details</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                    <th className="px-6 py-3">Date</th>
                    <th className="px-4 py-3">Symbol</th>
                    <th className="px-4 py-3">Exit Reason</th>
                    <th className="px-4 py-3">PnL</th>
                    <th className="px-4 py-3">Post 1h</th>
                    <th className="px-4 py-3">Post 24h</th>
                  </tr>
                </thead>
                <tbody>
                  {sells.slice(0, 50).map((row, i) => (
                    <tr key={i} className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors">
                      <td className="px-6 py-3 text-xs font-mono text-on-surface-variant">{row.sold_at || "-"}</td>
                      <td className="px-4 py-3 text-sm font-semibold">{(row.symbol || "").replace("KRW-", "")}</td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          row.exit_reason === "STOP_LOSS" ? "bg-error/10 text-error" : "bg-tertiary/10 text-tertiary"
                        }`}>{row.exit_reason || "-"}</span>
                      </td>
                      <td className={`px-4 py-3 text-sm font-mono ${
                        row.pnl_pct == null ? "text-on-surface-variant" : row.pnl_pct >= 0 ? "text-tertiary" : "text-error"
                      }`}>
                        {row.pnl_pct != null ? `${row.pnl_pct >= 0 ? "+" : ""}${row.pnl_pct.toFixed(2)}%` : "N/A"}
                      </td>
                      <td className={`px-4 py-3 text-sm font-mono ${
                        row.post_1h_pct == null ? "text-on-surface-variant" : row.post_1h_pct >= 0 ? "text-tertiary" : "text-error"
                      }`}>
                        {row.post_1h_pct != null ? `${row.post_1h_pct >= 0 ? "+" : ""}${row.post_1h_pct.toFixed(2)}%` : "N/A"}
                      </td>
                      <td className={`px-4 py-3 text-sm font-mono ${
                        row.post_24h_pct == null ? "text-on-surface-variant" : row.post_24h_pct >= 0 ? "text-tertiary" : "text-error"
                      }`}>
                        {row.post_24h_pct != null ? `${row.post_24h_pct >= 0 ? "+" : ""}${row.post_24h_pct.toFixed(2)}%` : "N/A"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
