import type { GroundingSource } from "../../lib/types";

/**
 * Google Maps attribution, placed immediately after the content it supports. The words
 * "Google Maps" are never restyled or translated (README, Constitution II).
 */
export default function SourceList({ sources }: { sources: GroundingSource[] }) {
  if (!sources.length) return null;
  return (
    <div className="sources" data-testid="sources">
      Source: <span translate="no">Google Maps</span>
      {" · "}
      {sources.map((s, i) => (
        <span key={s.uri}>
          {i > 0 && ", "}
          <a href={s.uri} target="_blank" rel="noopener noreferrer">
            {s.title}
          </a>
        </span>
      ))}
    </div>
  );
}
