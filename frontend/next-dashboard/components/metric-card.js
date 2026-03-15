export function MetricCard({ label, value, tone = "neutral", hint }) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <p className="metric-label">{label}</p>
      <strong className="metric-value">{value}</strong>
      {hint ? <p className="metric-hint">{hint}</p> : null}
    </article>
  );
}
