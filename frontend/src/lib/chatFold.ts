// Folding one streamed ADK event into the answer being built (tasks T070, T076).
import type { AgentEvent } from "./agentClient";
import { collectLiveChecks, collectReferences } from "./grounding";
import type { GroundingMetadata, LiveCheckReport, Report } from "./types";

export interface Fold {
  text: string;
  grounding?: GroundingMetadata;
  shelterIds: string[];
  countyFips: string[];
  liveChecks: LiveCheckReport[];
  tools: string[];
  report?: Report;
}

export const emptyFold: Fold = { text: "", shelterIds: [], countyFips: [], liveChecks: [], tools: [] };

const union = (a: string[], b: string[]) => (b.length ? [...new Set([...a, ...b])] : a);

function reportOf(response: unknown): Report | undefined {
  const r = (response as { report?: Report } | null)?.report;
  return r && typeof r === "object" && r.report_version === 1 && r.sections ? r : undefined;
}

export function foldEvent(acc: Fold, e: AgentEvent): Fold {
  let { text, grounding, shelterIds, countyFips, liveChecks, tools, report } = acc;
  for (const part of e.content?.parts ?? []) {
    if (part.functionCall?.name) tools = union(tools, [part.functionCall.name]);
    if (part.functionResponse) {
      if (part.functionResponse.name) tools = union(tools, [part.functionResponse.name]);
      const refs = collectReferences(part.functionResponse.response);
      shelterIds = union(shelterIds, refs.shelterIds);
      countyFips = union(countyFips, refs.countyFips);
      const checks = collectLiveChecks(part.functionResponse.response);
      if (checks.length) liveChecks = [...liveChecks, ...checks];
      report = reportOf(part.functionResponse.response) ?? report;
    }
  }
  const chunk = (e.content?.parts ?? []).map((p) => p.text ?? "").join("");
  if (chunk && e.author !== "user") {
    // Partial events carry deltas; a non-partial event carries the whole text so far.
    text = e.partial ? text + chunk : chunk;
  }
  if (e.groundingMetadata) grounding = e.groundingMetadata;
  return { text, grounding, shelterIds, countyFips, liveChecks, tools, report };
}
