import type { Report, ReportFigure } from "../../lib/types";

const TITLES: Record<string, string> = {
  who_cannot_leave: "Who cannot leave",
  power_outage: "Power outage",
  people_at_risk: "People at risk",
  where_they_would_go: "Where they would go",
  what_to_fix: "What to fix",
  storm_history: "Storm history",
  planner_updates: "Planner updates",
  could_not_tell: "What we could not tell",
  audit: "Audit",
};
const RANGE_LABELS: Record<string, string> = {
  typical: "typical",
  one_in_10: "1-in-10",
  one_in_100: "1-in-100",
  p10: "low",
  p50: "middle",
  p90: "high",
};

const fmt = (v: number, unit: string) =>
  unit === "share" ? `${(v * 100).toFixed(1)}%` : Math.round(v).toLocaleString("en-US");

function figureValue(f: ReportFigure): string {
  if (f.value !== null) return fmt(f.value, f.unit);
  return Object.entries(f.range ?? {})
    .map(([k, v]) => `${RANGE_LABELS[k] ?? k} ${fmt(v, f.unit)}`)
    .join(" · ");
}

export default function ReportView({ report }: { report: Report }) {
  return (
    <section className="report" data-testid="report" aria-label={`${report.scope} report`}>
      <div className="report__head">
        Report · {report.scope}
        {report.season?.label && <span className="report__season"> · {report.season.label}</span>}
      </div>
      {Object.entries(report.sections).map(([key, s]) => (
        <div key={key} className="report__section" data-status={s.status}>
          <div className="report__title">{TITLES[key] ?? key}</div>
          {s.status !== "ok" ? (
            <div className="status">{s.reason ?? s.status.replace("_", " ")}</div>
          ) : (
            <>
              {s.figures.map((f) => (
                <div key={f.key} className="report__figure" title={f.source}>
                  <span>{f.label}</span>
                  <strong>{figureValue(f)}</strong>
                  <span className="report__prov">{f.provenance}</span>
                </div>
              ))}
              {s.note && <div className="status">{s.note}</div>}
            </>
          )}
        </div>
      ))}
    </section>
  );
}
