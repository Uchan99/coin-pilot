const LABELS = {
  fresh: "Fresh",
  delayed: "Delayed",
  stale: "Stale",
  failed: "Failed",
  "manual-only": "Manual"
};

export function StatusPill({ status }) {
  const normalized = status || "failed";
  return (
    <span className={`status-pill status-${normalized}`}>
      {LABELS[normalized] || normalized}
    </span>
  );
}
