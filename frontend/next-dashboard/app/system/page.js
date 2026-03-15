import { MetricCard } from "@/components/metric-card";
import { SectionFrame } from "@/components/section-frame";
import { getSystemSnapshot } from "@/lib/bot-api";

export default async function SystemPage() {
  const system = await getSystemSnapshot();
  const components = Object.entries(system.components || {});

  return (
    <main className="content-grid">
      <SectionFrame
        eyebrow="Diagnostic"
        title="System Health"
        description="DB / Redis / n8n / bot 연결성을 기존 mobile status API 기준으로 다시 배치한 화면입니다."
        freshnessStatus={system.freshnessStatus}
        dataAgeSec={system.dataAgeSec}
        staleThresholdSec={system.staleThresholdSec}
      >
        {system.error ? <p className="callout error">{system.error}</p> : null}
        <div className="metrics-grid">
          <MetricCard
            label="Overall"
            value={system.overallStatus || "UNKNOWN"}
            tone={system.overallStatus === "UP" ? "good" : "warn"}
          />
          <MetricCard
            label="Risk Level"
            value={system.riskLevel || "UNKNOWN"}
            tone={system.riskLevel === "HIGH_RISK" ? "warn" : "neutral"}
          />
        </div>
      </SectionFrame>

      <SectionFrame
        eyebrow="Diagnostic"
        title="Components"
        description="22 spec의 System 페이지 원칙에 맞춰 연결 상태와 상세 사유를 같은 패널 내에서 분리 노출합니다."
        freshnessStatus={system.freshnessStatus}
        dataAgeSec={system.dataAgeSec}
        staleThresholdSec={system.staleThresholdSec}
      >
        <div className="component-grid">
          {components.map(([name, info]) => (
            <article key={name} className="component-card">
              <p className="component-name">{name}</p>
              <strong className={info.status === "UP" ? "tone-good" : "tone-warn"}>
                {info.status}
              </strong>
              <p className="component-detail">{info.detail || "detail 없음"}</p>
            </article>
          ))}
        </div>
      </SectionFrame>

      <SectionFrame
        eyebrow="Diagnostic"
        title="Risk Flags"
        description="운영 해석을 보조하는 상태 설명만 노출하고, 매매 판단 자체는 backend가 계속 소유합니다."
        freshnessStatus={system.freshnessStatus}
        dataAgeSec={system.dataAgeSec}
        staleThresholdSec={system.staleThresholdSec}
      >
        <ul className="flag-list">
          {(system.riskFlags || []).map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      </SectionFrame>
    </main>
  );
}
