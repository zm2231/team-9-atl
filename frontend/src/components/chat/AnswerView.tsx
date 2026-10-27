import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { segmentAnswer } from "../../lib/grounding";
import type { ChatExchange } from "../../lib/types";
import { useStore } from "../../state/store";
import SourceList from "./SourceList";

/**
 * Live (grounded) segments are marked and followed directly by their sources; everything else is
 * registry or agent reasoning (FR-012, FR-013).
 *
 * Accepted limitation (T045): the live/registry split is applied per segment, so a markdown table
 * or list that spans a segment boundary renders as separate blocks.
 */
export default function AnswerView({ exchange, onRetry }: { exchange: ChatExchange; onRetry: () => void }) {
  const { dispatch, shelterById, countyByFips } = useStore();
  const segments = segmentAnswer(exchange.text, exchange.groundingMetadata);

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
          {exchange.referenced_county_fips.map((f) => (
            <button key={f} type="button" className="chip" onClick={() => dispatch({ type: "selectCounty", fips: f })}>
              {countyByFips.get(f)?.name ?? f} County
            </button>
          ))}
          {exchange.referenced_shelter_ids.map((id) => (
            <button key={id} type="button" className="chip" onClick={() => dispatch({ type: "selectShelter", id })}>
              {shelterById.get(id)?.name ?? id}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
