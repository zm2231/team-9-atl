import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent } from "../../lib/agentClient";
import { collectReferences } from "../../lib/grounding";
import type { ChatContext, ChatExchange, GroundingMetadata, HurricaneScenario } from "../../lib/types";
import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import AnswerView from "./AnswerView";

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

  // Typing moves the pointer off the map, so fall back to the last county hovered (FR-011).
  const contextFips = state.selectedFips ?? state.lastHoverFips;
  const countyName = contextFips ? countyByFips.get(contextFips)?.name : undefined;

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [state.chat]);

  async function run(question: string, context: ChatContext, id: string) {
    let text = "";
    let grounding: GroundingMetadata | undefined;
    const shelterIds = new Set<string>();
    const countyFips = new Set<string>();
    const update = (patch: Partial<ChatExchange>) => dispatch({ type: "chatUpdate", id, patch });

    try {
      await streamChat({
        question,
        context,
        onEvent: (e: AgentEvent) => {
          for (const part of e.content?.parts ?? []) {
            if (part.functionResponse) {
              const refs = collectReferences(part.functionResponse.response);
              refs.shelterIds.forEach((s) => shelterIds.add(s));
              refs.countyFips.forEach((f) => countyFips.add(f));
            }
          }
          const chunk = (e.content?.parts ?? []).map((p) => p.text ?? "").join("");
          if (chunk && e.author !== "user") {
            // Partial events carry deltas; the final event carries the whole text.
            text = e.partial ? text + chunk : chunk;
          }
          if (e.groundingMetadata) grounding = e.groundingMetadata;
          update({
            status: "streaming",
            text,
            groundingMetadata: grounding,
            referenced_shelter_ids: [...shelterIds],
            referenced_county_fips: [...countyFips],
          });
        },
      });
      update({ status: "done" });
      dispatch({ type: "highlight", shelterIds: [...shelterIds], countyFips: [...countyFips] });
      // Keep only place ids for shelters the answer referred to and Maps named (FR-022).
      for (const sid of shelterIds) {
        const name = shelterById.get(sid)?.name.toLowerCase();
        const placeIds = (grounding?.groundingChunks ?? [])
          .map((c) => c.maps)
          .filter((m) => m?.placeId && name && m.title?.toLowerCase().includes(name))
          .map((m) => m!.placeId!);
        if (placeIds.length) dispatch({ type: "liveCheck", shelterId: sid, placeIds });
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
      <div className="chat__log" ref={logRef}>
        <h2>Ask the agent</h2>
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
