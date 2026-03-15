import { StatusPill } from "@/components/status-pill";

export function SectionFrame({
  eyebrow,
  title,
  description,
  freshnessStatus,
  dataAgeSec,
  staleThresholdSec,
  children
}) {
  return (
    <section className="section-frame">
      <div className="section-header">
        <div>
          <p className="section-eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          <p className="section-description">{description}</p>
        </div>
        <div className="section-meta">
          <StatusPill status={freshnessStatus} />
          <span className="section-age">
            age {dataAgeSec ?? "-"}s / threshold {staleThresholdSec ?? "-"}s
          </span>
        </div>
      </div>
      {children}
    </section>
  );
}
