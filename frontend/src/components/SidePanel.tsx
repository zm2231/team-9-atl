import { useRef, type KeyboardEvent } from "react";
import { useStore, type SideTab } from "../state/store";
import ChatPanel from "./chat/ChatPanel";
import DetailsPanel from "./summary/DetailsPanel";

const TABS: { id: SideTab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "details", label: "Details" },
];

/**
 * Chat and Details share one always-open panel (feature 003 FR-008–FR-014). Both tabs stay mounted
 * so typed text, scroll position and a streaming answer survive a switch (research R5).
 */
export default function SidePanel() {
  const { state, dispatch } = useStore();
  const refs = useRef<Partial<Record<SideTab, HTMLButtonElement | null>>>({});

  const select = (tab: SideTab) => {
    dispatch({ type: "setSideTab", tab });
    refs.current[tab]?.focus();
  };

  const onKeyDown = (e: KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === state.sideTab);
    const to = {
      ArrowRight: TABS[(i + 1) % TABS.length],
      ArrowLeft: TABS[(i - 1 + TABS.length) % TABS.length],
      Home: TABS[0],
      End: TABS[TABS.length - 1],
    }[e.key];
    if (!to) return;
    e.preventDefault();
    select(to.id);
  };

  return (
    <aside id="side-panel" className="side-panel" aria-label="Chat and details">
      <div className="side-panel__tabs" role="tablist" aria-label="Side panel" onKeyDown={onKeyDown}>
        {TABS.map((t) => {
          const selected = state.sideTab === t.id;
          const unseen = t.id === "details" && state.detailsUnseen;
          return (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              id={`tab-${t.id}`}
              type="button"
              role="tab"
              className="side-tab"
              aria-selected={selected}
              aria-controls={`panel-${t.id}`}
              aria-label={unseen ? `${t.label} (new details available)` : undefined}
              tabIndex={selected ? 0 : -1}
              onClick={() => dispatch({ type: "setSideTab", tab: t.id })}
            >
              {t.label}
              {unseen && <span className="side-tab__dot" aria-hidden="true" />}
            </button>
          );
        })}
      </div>
      <div
        id="panel-chat"
        role="tabpanel"
        aria-labelledby="tab-chat"
        className="side-panel__panel"
        hidden={state.sideTab !== "chat"}
      >
        <ChatPanel active={state.sideTab === "chat"} />
      </div>
      <div
        id="panel-details"
        role="tabpanel"
        aria-labelledby="tab-details"
        className="side-panel__panel side-panel__panel--scroll"
        hidden={state.sideTab !== "details"}
      >
        <DetailsPanel />
      </div>
    </aside>
  );
}
