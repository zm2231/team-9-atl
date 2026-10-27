import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent } from "../../lib/agentClient";
import { emptyFold, foldEvent, type Fold } from "../../lib/chatFold";
import type { ChatContext, ChatExchange, HurricaneScenario } from "../../lib/types";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import AnswerView from "./AnswerView";
import EarlierQuestions from "./EarlierQuestions";
import HistorySection from "./HistorySection";

const RECEIVING_TOP = 20;

export function buildContext(
  county_fips: string | null,
  shelter_id: string | null,
  scenario: HurricaneScenario | null,
): ChatContext {
  return {
    county_fips,
    shelter_id,
    scenario: scenario && {
      track: scenario.track,
      category: scenario.category,
      cutoff_km: scenario.cutoff_km,
      affected_county_fips: scenario.affected_county_fips,
      affected_shelter_ids: scenario.affected_shelter_ids,
      receiving_top: scenario.receiving.slice(0, RECEIVING_TOP).map((r) => r.shelter_id),
    },
  };
}

export default function ChatPanel() {
  const { state, dispatch, countyByFips, shelterById } = useStore();
  const scenario = useScenario();
  const [input, setInput] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const busy = state.chat.some((c) => c.status === "pending" || c.status === "streaming");
  const current = state.currentScenarioId
    ? state.history.find((h) => h.id === state.currentScenarioId)
    : undefined;

  // Typing moves the pointer off the map, so fall back to the last county hovered (FR-011).
  const contextFips = state.selectedFips ?? state.lastHoverFips;
  const countyName = contextFips ? countyByFips.get(contextFips)?.name : undefined;

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [state.chat]);

  async function run(question: string, context: ChatContext, id: string) {
    let acc: Fold = emptyFold;
    const update = (patch: Partial<ChatExchange>) => dispatch({ type: "chatUpdate", id, patch });

    try {
      await streamChat({
        question,
        context,
        onSession: (sessionId) => dispatch({ type: "chatSession", sessionId }),
        onEvent: (e: AgentEvent) => {
          acc = foldEvent(acc, e);
          update({
            status: "streaming",
            text: acc.text,
            groundingMetadata: acc.grounding,
            referenced_shelter_ids: acc.shelterIds,
            referenced_county_fips: acc.countyFips,
          });
        },
      });
      update({ status: "done" });
      dispatch({ type: "highlight", shelterIds: acc.shelterIds, countyFips: acc.countyFips });
      // The agent reports each grounded shelter via record_live_check; keep only status and
      // place id for the session (FR-022).
      for (const lc of acc.liveChecks) {
        if (!shelterById.has(lc.shelter_id)) continue;
        dispatch({
          type: "liveCheck",
          shelterId: lc.shelter_id,
          status: lc.status,
          placeIds: lc.place_id ? [lc.place_id] : [],
        });
      }
    } catch (e) {
      update({ status: "failed", error: e instanceof Error ? e.message : String(e) });
    }
  }

  function ask(question: string, context?: ChatContext) {
    const q = question.trim();
    if (!q || busy) return;
    const ctx = context ?? buildContext(contextFips, state.selectedShelterId, scenario);
    const id = `x-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    dispatch({
      type: "chatStart",
      exchange: { id, question: q, context: ctx, status: "pending", text: "", referenced_shelter_ids: [], referenced_county_fips: [] },
    });
    setInput("");
    void run(q, ctx, id);
  }

  const suggestions: string[] = [];
  if (countyName) {
    suggestions.push(
      `How many shelters are in ${countyName} County and what is their capacity?`,
      `Which shelters in ${countyName} County are in the surge zone?`,
      `What should I verify before September in ${countyName} County?`,
    );
  }
  if (scenario) suggestions.push("Which of these receiving shelters can actually take a wheelchair?");

  return (
    <aside className="chat" aria-label="Ask the agent">
      <HistorySection />
      <div className="chat__log" ref={logRef}>
        <h2>Ask the agent</h2>
        {current && state.resimulatedAt && (
          <EarlierQuestions
            questions={current.questions}
            resimulatedAt={state.resimulatedAt}
            onAsk={(text) => ask(text)}
            disabled={busy}
          />
        )}
        {state.chat.length === 0 && (
          <p className="muted small">
            Ask about a county, a shelter or the simulated hurricane. The selected county
            {scenario ? ", the scenario" : ""} and any selected shelter are sent as context.
          </p>
        )}
        {state.chat.map((x) => (
          <div key={x.id}>
            <div className="q">{x.question}</div>
            <AnswerView exchange={x} onRetry={() => ask(x.question, x.context)} />
          </div>
        ))}
      </div>
      {suggestions.length > 0 && (
        <div className="chips">
          {suggestions.map((s) => (
            <button key={s} type="button" className="chip" disabled={busy} onClick={() => ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="chat__form"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={countyName ? `Ask about ${countyName} County…` : "Ask about a county or shelter…"}
          aria-label="Question for the agent"
        />
        <button type="submit" className="btn" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  );
}
