import { useState } from "react";
import { resetChatSession } from "../../lib/agentClient";
import { countyNames } from "../../lib/geo";
import { abbreviateCounties, relativeTime, type SavedScenario } from "../../lib/history";
import { countiesAlongTrack } from "../../lib/simulation";
import { useStore } from "../../state/store";

/** Crossed-county names per track, memoised: sampling 50 tracks on every render adds up. */
const countyCache = new WeakMap<SavedScenario["track"], string>();
function crossedCounties(track: SavedScenario["track"]): string {
  let v = countyCache.get(track);
  if (v === undefined) {
    v = abbreviateCounties(countiesAlongTrack(track).map((f) => countyNames.get(f) ?? f));
    countyCache.set(track, v);
  }
  return v;
}

function HistoryItem({ s, current, busy, now }: { s: SavedScenario; current: boolean; busy: boolean; now: Date }) {
  const { dispatch } = useStore();
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(s.name);
  const [confirming, setConfirming] = useState(false);

  const commit = () => {
    dispatch({ type: "renameScenario", id: s.id, name: draft });
    setRenaming(false);
  };

  return (
    <li className={`history-item${current ? " history-item--current" : ""}`}>
      {renaming ? (
        <input
          className="history-item__input"
          aria-label="Scenario name"
          maxLength={80}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setDraft(s.name);
              setRenaming(false);
            }
          }}
          onBlur={commit}
        />
      ) : (
        <button
          type="button"
          className="history-item__open"
          data-testid="history-item"
          aria-current={current ? "true" : undefined}
          disabled={busy && !current}
          onClick={() => {
            if (current) return;
            dispatch({ type: "openScenario", id: s.id });
            resetChatSession();
          }}
        >
          <span className="history-item__name">{s.name}</span>
          <span className="history-item__meta">
            <span className="kind kind--simulation">Cat {s.category}</span> {crossedCounties(s.track) || "offshore"} ·{" "}
            {relativeTime(s.last_opened_at, now)}
          </span>
        </button>
      )}
      {confirming ? (
        <div className="history-item__confirm" role="group" aria-label={`Delete ${s.name}`}>
          <span>Delete '{s.name}'?</span>
          <button
            type="button"
            className="btn"
            onClick={() => {
              dispatch({ type: "deleteScenario", id: s.id });
              if (current) resetChatSession();
            }}
          >
            Delete
          </button>
          <button type="button" className="btn" onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      ) : (
        !renaming && (
          <div className="history-item__actions">
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                setDraft(s.name);
                setRenaming(true);
              }}
            >
              Rename
            </button>
            <button type="button" className="link-btn" onClick={() => setConfirming(true)}>
              Delete
            </button>
          </div>
        )
      )}
    </li>
  );
}

/** Scenario history at the top of the chat column (feature 002, contracts/history-ui.md). */
export default function HistorySection() {
  const { state, dispatch } = useStore();
  const [open, setOpen] = useState(false);
  const busy = state.chat.some((c) => c.status === "pending" || c.status === "streaming");
  const now = new Date();
  const list = [...state.history].sort((a, b) => b.last_opened_at.localeCompare(a.last_opened_at));

  return (
    <section className="history" aria-label="Scenario history">
      <button
        type="button"
        className="history__header"
        aria-expanded={open}
        aria-controls="history-list"
        onClick={() => setOpen((o) => !o)}
      >
        History ({state.history.length}) {open ? "▾" : "▸"}
      </button>
      {open && (
        <div className="history__body">
          {state.notice && (
            <div className="history__notice" role="status">
              {state.notice}{" "}
              <button type="button" className="link-btn" onClick={() => dispatch({ type: "dismissNotice" })}>
                Dismiss
              </button>
            </div>
          )}
          {list.length === 0 ? (
            <p className="muted small">No saved scenarios yet. Draw a hurricane track to start one.</p>
          ) : (
            <ul id="history-list" className="history__list">
              {list.map((s) => (
                <HistoryItem key={s.id} s={s} current={s.id === state.currentScenarioId} busy={busy} now={now} />
              ))}
            </ul>
          )}
          <p className="history__note">
            {state.historyAvailable
              ? "Saved in this browser only, including the questions you type."
              : "History can't be saved in this browser."}
          </p>
        </div>
      )}
    </section>
  );
}
