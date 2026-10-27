import { useEffect, useState } from "react";
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

function FigureValue({ f }: { f: ReportFigure }) {
  if (f.value !== null) return <strong>{fmt(f.value, f.unit)}</strong>;
  const r = f.range ?? {};
  const keys = f.range_kind === "season" ? ["typical", "one_in_10", "one_in_100"] : ["p10", "p50", "p90"];
  const [lo, mid, hi] = keys.map((k) => r[k]);
  if (mid === undefined) {
    return <strong>{Object.entries(r).map(([k, v]) => `${RANGE_LABELS[k] ?? k} ${fmt(v, f.unit)}`).join(" · ")}</strong>;
  }
  const top = Math.max(hi ?? mid, 1e-9);
  const pct = (v: number | undefined) => `${Math.max(0, Math.min(100, ((v ?? 0) / top) * 100))}%`;
  return (
    <span className="report__range">
      <strong>
        {fmt(mid, f.unit)} <small>{RANGE_LABELS[keys[1]]}</small>
      </strong>
      <span className="report__bar" aria-hidden="true">
        <span style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
        <i style={{ left: pct(mid) }} />
      </span>
      <small>
        {RANGE_LABELS[keys[0]]} {fmt(lo ?? 0, f.unit)} · {RANGE_LABELS[keys[2]]} {fmt(hi ?? 0, f.unit)}
      </small>
    </span>
  );
}

const SUPPORT: Record<string, string> = {
  within_labeled_support: "inside the range of storms with outage records",
  outside_labeled_support: "outside the range of storms with outage records",
};

function readableNote(note: string): string {
  return note.replace(/\b(within|outside)_labeled_support\b/g, (m) => SUPPORT[m] ?? m);
}

function TextItems({ items }: { items: unknown[] }) {
  const lines = items.filter((i): i is string => typeof i === "string");
  if (!lines.length) return null;
  return (
    <ul className="report__list">
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

interface CountyOutage {
  county_fips: string;
  county_name: string;
  outage_share?: { p10?: number; p50?: number; p90?: number };
}

function TopCounties({ items }: { items: unknown[] }) {
  const rows = (items as CountyOutage[])
    .filter((c) => c.outage_share?.p50 !== undefined)
    .sort((a, b) => (b.outage_share!.p50 ?? 0) - (a.outage_share!.p50 ?? 0))
    .slice(0, 10);
  if (!rows.length) return null;
  const p = (v?: number) => (v === undefined ? "–" : `${Math.round(v * 100)}%`);
  return (
    <table className="report__counties" data-testid="report-counties">
      <thead>
        <tr>
          <th>Most affected counties</th>
          <th>middle</th>
          <th>low – high</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr key={c.county_fips}>
            <td>{c.county_name}</td>
            <td>{p(c.outage_share!.p50)}</td>
            <td>
              {p(c.outage_share!.p10)} – {p(c.outage_share!.p90)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ReportView({ report }: { report: Report }) {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);
  return (
    <section
      className={expanded ? "report report--expanded" : "report"}
      data-testid="report"
      aria-label={`${report.scope} report`}
      aria-modal={expanded || undefined}
      role={expanded ? "dialog" : undefined}
    >
      <div className="report__head">
        Report · {report.scope}
        {report.season?.label && <span className="report__season"> · {report.season.label}</span>}
        <button
          type="button"
          className="btn report__expand"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "Close full-screen report" : "Open report full screen"}
        >
          {expanded ? "✕ Close" : "⤢ Expand"}
        </button>
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
                  <FigureValue f={f} />
                  <span className="report__prov">{f.provenance}</span>
                </div>
              ))}
              {key === "power_outage" && <TopCounties items={s.items} />}
              <TextItems items={s.items} />
              {s.note && <div className="status">{readableNote(s.note)}</div>}
            </>
          )}
        </div>
      ))}
    </section>
  );
}
