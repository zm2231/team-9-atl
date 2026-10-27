import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { segmentAnswer } from "../../lib/grounding";
import type { ChatExchange } from "../../lib/types";
import { useStore } from "../../state/store";
import ReportView from "./ReportView";
import SourceList from "./SourceList";

/**
 * Live (grounded) segments are marked and followed directly by their sources; everything else is
 * registry or agent reasoning (FR-012, FR-013).
 *
 * Accepted limitation (T045): the live/registry split is applied per segment, so a markdown table
 * or list that spans a segment boundary renders as separate blocks.
 */
const CHIP_LIMIT = 8;

export default function AnswerView({ exchange, onRetry }: { exchange: ChatExchange; onRetry: () => void }) {
  const { dispatch, shelterById, countyByFips } = useStore();
  const segments = segmentAnswer(exchange.text, exchange.groundingMetadata);
  const [allRefs, setAllRefs] = useState(false);
  const refCount = exchange.referenced_county_fips.length + exchange.referenced_shelter_ids.length;
  const countyRefs = allRefs ? exchange.referenced_county_fips : exchange.referenced_county_fips.slice(0, CHIP_LIMIT);
  const shelterRefs = allRefs
    ? exchange.referenced_shelter_ids
    : exchange.referenced_shelter_ids.slice(0, Math.max(0, CHIP_LIMIT - countyRefs.length));

  return (
    <div className="answer" data-testid="answer">
      {segments.map((seg, i) =>
        seg.kind === "live" ? (
          <div key={i}>
            <div className="seg-live" data-kind="live">
              <span className="seg-live__badge">Live check · just now</span>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{seg.text}</ReactMarkdown>
            </div>
            <SourceList sources={seg.sources ?? []} />
          </div>
        ) : (
          <div key={i} data-kind="registry">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{seg.text}</ReactMarkdown>
          </div>
        ),
      )}

      {exchange.report && <ReportView report={exchange.report} />}

      {exchange.tools_used && exchange.tools_used.length > 0 && (
        <div className="tools-used" data-testid="tools-used">
          <span className="tools-used__label">Tools called</span>
          {exchange.tools_used.map((t) => (
            <code key={t} className="tools-used__tool">
              {t}
            </code>
          ))}
        </div>
      )}

      {exchange.status === "pending" && <div className="status">Asking the agent…</div>}
      {exchange.status === "streaming" && <div className="status">Answering…</div>}
      {exchange.status === "failed" && (
        <div className="status status--failed" role="alert">
          The agent could not answer: {exchange.error}{" "}
          <button type="button" className="btn" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}

      {(exchange.referenced_shelter_ids.length > 0 || exchange.referenced_county_fips.length > 0) && (
        <div className="chips" style={{ padding: "4px 0" }}>
          {countyRefs.map((f) => (
            <button key={f} type="button" className="chip" onClick={() => dispatch({ type: "selectCounty", fips: f })}>
              {countyByFips.get(f)?.name ?? f} County
            </button>
          ))}
          {shelterRefs.map((id) => (
            <button key={id} type="button" className="chip" onClick={() => dispatch({ type: "selectShelter", id })}>
              {shelterById.get(id)?.name ?? id}
            </button>
          ))}
          {refCount > CHIP_LIMIT && (
            <button type="button" className="chip" onClick={() => setAllRefs((v) => !v)}>
              {allRefs ? "Show fewer" : `+${refCount - CHIP_LIMIT} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
