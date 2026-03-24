"use client";
import PlotlyChart from "@/components/plotly-chart";

/*
 * Exit Analysis 페이지 — Stitch 디자인
 * KPI 4카드 + 박스플롯(PnL by Exit Reason) + 라인(Post-Exit) + 히트맵(Regime×Reason) + 튜닝 제안 + 상세 테이블
 * 현재 Phase 2 MVP: Mock 데이터 기반 UI 프레임
 */

const KPI = [
  { label: "Sell Count", value: "1,482", sub: "최근 30일", icon: "sell" },
  { label: "PnL Computable Count", value: "1,240", sub: "Entry 데이터 있음", icon: "calculate" },
  { label: "Post 24h Samples", value: "912", sub: "24시간 추적 완료", icon: "schedule" },
  { label: "Avg Sell PnL (%)", value: "+4.82%", sub: "평균 실현 손익", icon: "trending_up", positive: true },
];

const EXIT_REASONS = ["TRAILING_STOP", "TAKE_PROFIT", "STOP_LOSS", "RSI_OVERBOUGHT", "TIME_LIMIT"];
const REGIMES = ["BULL", "SIDEWAYS", "BEAR"];

// 히트맵 mock 데이터
const heatmapZ = [
  [2.1, 5.3, -3.2, 1.8, -0.5],
  [-0.9, 3.1, -2.7, 0.8, -1.4],
  [-2.1, -0.8, -7.4, -3.5, -2.5],
];

const TUNING_SUGGESTIONS = [
  { icon: "tune", severity: "warning", text: "Trailing Stop을 현 3%에서 2.5%로 타이트닝 검토" },
  { icon: "analytics", severity: "info", text: "RSI Overbought 청산은 SIDEWAYS에서 과조기 패턴 — 70→75 기준 조정 권장" },
  { icon: "verified", severity: "info", text: "Take Profit 성과가 레짐 무관하게 양호 — 현 설정 유지" },
];

export default function ExitAnalysisPage() {
  // 박스플롯 mock
  const boxData = EXIT_REASONS.map((reason) => ({
    y: Array.from({ length: 20 }, () => (Math.random() - 0.3) * 10),
    name: reason,
    type: "box",
    boxpoints: "all",
    jitter: 0.3,
    pointpos: -1.8,
    marker: { size: 3 },
  }));

  // Post-exit 라인 mock
  const windows = ["1h", "4h", "12h", "24h"];
  const avgChanges = [0.2, -0.3, -0.8, -1.2];

  return (
    <div className="space-y-6">
      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {KPI.map(({ label, value, sub, icon, positive }) => (
          <div key={label} className="bg-surface-container p-5 rounded-xl border border-outline-variant/10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">{label}</span>
              <span className="material-symbols-outlined text-primary/40 text-lg">{icon}</span>
            </div>
            <div className={`text-2xl font-bold tracking-tight ${positive ? "text-tertiary" : "text-on-surface"}`}>
              {value}
            </div>
            <div className="text-xs text-on-surface-variant mt-1">{sub}</div>
          </div>
        ))}
      </div>

      {/* 차트 2열 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 박스플롯 */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2 px-2">
            PnL Distribution by Exit Reason
          </h4>
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
              text: avgChanges.map((v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`),
              textposition: "top center",
              textfont: { color: "#c2c6d6", size: 10 },
              line: { color: "#4ae176", width: 2 },
              marker: { color: "#4ae176", size: 8 },
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

      {/* 히트맵 + 튜닝 제안 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 히트맵 */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-4">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2 px-2">
            Regime × Exit Performance Matrix
          </h4>
          <PlotlyChart
            data={[{
              z: heatmapZ,
              x: EXIT_REASONS,
              y: REGIMES,
              type: "heatmap",
              colorscale: [
                [0, "#93000a"],
                [0.5, "#2a3548"],
                [1, "#00a74b"],
              ],
              zmid: 0,
              text: heatmapZ.map((row) => row.map((v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`)),
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

        {/* 튜닝 제안 */}
        <div className="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
          <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-4">
            Tuning Suggestions
          </h4>
          <div className="space-y-4">
            {TUNING_SUGGESTIONS.map(({ icon, severity, text }, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className={`material-symbols-outlined text-lg mt-0.5 ${
                  severity === "warning" ? "text-yellow-400" : "text-primary"
                }`}>
                  {icon}
                </span>
                <p className="text-sm text-on-surface-variant leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

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
              {[
                { date: "03-24", sym: "BTC", reason: "TRAILING_STOP", pnl: "+1.2%", p1h: "-0.3%", p24h: "-1.5%" },
                { date: "03-23", sym: "ETH", reason: "TAKE_PROFIT", pnl: "+3.4%", p1h: "+0.1%", p24h: "-0.8%" },
                { date: "03-23", sym: "SOL", reason: "STOP_LOSS", pnl: "-4.1%", p1h: "+0.5%", p24h: "+1.2%" },
                { date: "03-22", sym: "XRP", reason: "RSI_OVERBOUGHT", pnl: "+0.8%", p1h: "-0.2%", p24h: "-2.1%" },
              ].map((row, i) => (
                <tr key={i} className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors">
                  <td className="px-6 py-3 text-xs font-mono text-on-surface-variant">{row.date}</td>
                  <td className="px-4 py-3 text-sm font-semibold">{row.sym}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      row.reason === "STOP_LOSS" ? "bg-error/10 text-error" : "bg-tertiary/10 text-tertiary"
                    }`}>{row.reason}</span>
                  </td>
                  <td className={`px-4 py-3 text-sm font-mono ${row.pnl.startsWith("+") ? "text-tertiary" : "text-error"}`}>{row.pnl}</td>
                  <td className={`px-4 py-3 text-sm font-mono ${row.p1h.startsWith("+") ? "text-tertiary" : "text-error"}`}>{row.p1h}</td>
                  <td className={`px-4 py-3 text-sm font-mono ${row.p24h.startsWith("+") ? "text-tertiary" : "text-error"}`}>{row.p24h}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
