import { useState } from "react";
import { relativeTime, type SavedQuestion } from "../../lib/history";

/**
 * The reopened scenario's earlier questions, each with "Ask again" (FR-009). Stays available for
 * the whole reopened session so any question can be re-asked (analysis H2), and says the results
 * were re-simulated where it is always visible (analysis M2).
 */
export default function EarlierQuestions({
  questions,
  resimulatedAt,
  onAsk,
  disabled,
}: {
  questions: SavedQuestion[];
  resimulatedAt: string;
  onAsk: (text: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(true);
  const now = new Date();
  const at = new Date(resimulatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="card earlier" data-testid="earlier-questions">
      <div className="small" data-testid="resimulated-note">
        <span className="kind kind--simulation">Re-simulated</span> Results re-simulated at {at} from current data.
      </div>
      {questions.length > 0 && (
        <>
          <button
            type="button"
            className="link-btn earlier__toggle"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            Earlier questions in this scenario ({questions.length}) {open ? "▾" : "▸"}
          </button>
          {open && (
            <ul className="earlier__list">
              {questions.map((q, i) => (
                <li key={`${q.asked_at}-${i}`} className="earlier__item">
                  <span>
                    {q.text} <span className="muted">· {relativeTime(q.asked_at, now)}</span>
                  </span>
                  <button type="button" className="btn" disabled={disabled} onClick={() => onAsk(q.text)}>
                    Ask again
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
