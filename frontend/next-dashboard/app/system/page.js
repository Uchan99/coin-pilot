import { getSystemSnapshot } from "@/lib/bot-api";

/*
 * System Health 페이지 — Stitch 디자인
 * Server Component: getSystemSnapshot()으로 컴포넌트 상태 조회
 * 3개 연결 상태 카드 + AI Decisions 테이블(목) + Risk Audit 테이블(목)
 */

export default async function SystemPage() {
  const data = await getSystemSnapshot();
  const components = data.components || {};

  const STATUS_COLORS = {
    UP: { dot: "bg-tertiary", text: "text-tertiary", label: "Connected" },
    DOWN: { dot: "bg-error", text: "text-error", label: "Error" },
    UNKNOWN: { dot: "bg-outline-variant", text: "text-on-surface-variant", label: "Unknown" },
  };

  const componentCards = [
    { name: "PostgreSQL", icon: "database", key: "db", sub: "Core Database" },
    { name: "Redis Cache", icon: "memory", key: "redis", sub: "Session & Cache" },
    { name: "n8n Workflow", icon: "account_tree", key: "n8n", sub: "Automation Engine" },
  ];

  const mockDecisions = [
    { time: "14:22:45.24", symbol: "KRW-BTC", decision: "REJECT", reasoning: "Strong RSI divergence on 15m candle with low confidence", confidence: 92, model: "gpt-4o" },
    { time: "13:31:18.06", symbol: "KRW-ETH", decision: "REJECT", reasoning: "Volatility index exceeds risk threshold. Liquidity...", confidence: 85, model: "Claude 3.5" },
    { time: "13:15:12.88", symbol: "KRW-SOL", decision: "APPROVE", reasoning: "Breakout of AI consolidation pattern with volume...", confidence: 94, model: "gpt-4o" },
  ];

  return (
    <div className="space-y-6">
      {/* 연결 상태 3카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {componentCards.map(({ name, icon, key, sub }) => {
          const comp = components[key] || {};
          const status = comp.status || "UNKNOWN";
          const sc = STATUS_COLORS[status] || STATUS_COLORS.UNKNOWN;
          return (
            <div key={key} className="bg-surface-container rounded-xl border border-outline-variant/10 p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-primary">{icon}</span>
                  <div>
                    <div className="font-semibold text-sm">{name}</div>
                    <div className="text-[10px] text-on-surface-variant">{sub}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${sc.text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                  {sc.label}
                </span>
              </div>
              {comp.detail && <div className="text-xs text-on-surface-variant">{comp.detail}</div>}
            </div>
          );
        })}
      </div>

      {/* Recent AI Decisions */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="font-bold">Recent AI Decisions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                <th className="px-6 py-3">Timestamp</th>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Reasoning</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Model</th>
              </tr>
            </thead>
            <tbody>
              {mockDecisions.map((d, i) => (
                <tr key={i} className="border-t border-outline-variant/5 hover:bg-surface-high/30 transition-colors">
                  <td className="px-6 py-4 text-xs font-mono text-on-surface-variant">{d.time}</td>
                  <td className="px-4 py-4 text-sm font-semibold">{d.symbol.replace("KRW-", "")}</td>
                  <td className="px-4 py-4">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      d.decision === "APPROVE" ? "bg-tertiary/10 text-tertiary" : "bg-error/10 text-error"
                    }`}>{d.decision}</span>
                  </td>
                  <td className="px-4 py-4 text-xs text-on-surface-variant max-w-[250px] truncate">{d.reasoning}</td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-surface-high rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${d.confidence}%` }} />
                      </div>
                      <span className="text-xs font-mono">{d.confidence}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-xs text-on-surface-variant">{d.model}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risk Audit Logs */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="px-6 py-4 border-b border-outline-variant/10">
          <h3 className="font-bold">Risk Audit Logs</h3>
        </div>
        <div className="px-6 py-8 text-center text-on-surface-variant text-sm flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-tertiary text-lg">check_circle</span>
          No risk violations recorded. This is good!
        </div>
      </div>

      {/* Manual Refresh */}
      <div className="flex justify-center">
        <button className="px-6 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold rounded-xl active:scale-95 transition-all shadow-lg shadow-primary/20">
          <span className="material-symbols-outlined align-middle mr-2 text-lg">refresh</span>
          Manual System Refresh
        </button>
      </div>
    </div>
  );
}
