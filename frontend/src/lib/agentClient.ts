// Frontend ↔ agent service (contracts/agent-interface.md). One origin; IAP handles identity.
import type { ChatContext, MapData } from "./types";

export const APP = "readiness_agent";
export const LOAD_MAP_DATA_COMMAND = "LOAD_MAP_DATA v1";
export const MAP_DATA_TIMEOUT_MS = 20_000; // SC-004a
export const CHAT_TIMEOUT_MS = 90_000;

const userId = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `u-${Date.now()}`;

/** The parts of an ADK event the UI reads (camelCase, verified against google-adk 2.13). */
export interface AgentEvent {
  author?: string;
  partial?: boolean;
  content?: { role?: string; parts?: { text?: string; functionResponse?: { name?: string; response?: unknown } }[] };
  groundingMetadata?: import("./types").GroundingMetadata;
  errorCode?: string;
  errorMessage?: string;
}

export async function createSession(signal?: AbortSignal): Promise<string> {
  const res = await fetch(`/apps/${APP}/users/${userId}/sessions`, { method: "POST", signal });
  if (!res.ok) throw new Error(`Could not start a session (HTTP ${res.status})`);
  const body = (await res.json()) as { id?: string };
  if (!body.id) throw new Error("Session response had no id");
  return body.id;
}

function withTimeout(ms: number, outer?: AbortSignal): { signal: AbortSignal; done: () => void } {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(new DOMException("Timed out", "TimeoutError")), ms);
  const onOuter = () => ctrl.abort(outer?.reason);
  outer?.addEventListener("abort", onOuter, { once: true });
  return {
    signal: ctrl.signal,
    done: () => {
      clearTimeout(timer);
      outer?.removeEventListener("abort", onOuter);
    },
  };
}

/** Session-start data load through the agent; no LLM call is made (contracts §2). */
export async function loadMapData(outer?: AbortSignal): Promise<MapData> {
  const { signal, done } = withTimeout(MAP_DATA_TIMEOUT_MS, outer);
  try {
    const sessionId = await createSession(signal);
    const res = await fetch("/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal,
      body: JSON.stringify({
        app_name: APP,
        user_id: userId,
        session_id: sessionId,
        new_message: { role: "user", parts: [{ text: LOAD_MAP_DATA_COMMAND }] },
      }),
    });
    if (!res.ok) throw new Error(`Map data request failed (HTTP ${res.status})`);
    const events = (await res.json()) as AgentEvent[];
    const last = [...events].reverse().find((e) => e.author === APP && e.content?.parts?.[0]?.text);
    if (!last) throw new Error("The agent returned no map data");
    let payload: MapData & { error?: string };
    try {
      payload = JSON.parse(last.content!.parts![0].text!);
    } catch {
      throw new Error("The agent's map data could not be read");
    }
    if (payload.error) throw new Error(`The agent could not load map data: ${payload.error}`);
    if (payload.schema !== "map-data/v1") throw new Error(`Unknown map data version: ${String(payload.schema)}`);
    return payload;
  } catch (e) {
    if (signal.aborted && (signal.reason as DOMException)?.name === "TimeoutError") {
      throw new Error("Map data did not arrive within 20 seconds");
    }
    throw e;
  } finally {
    done();
  }
}

let chatSession: Promise<string> | null = null;

export function contextPart(context: ChatContext): string {
  return `CONTEXT v1 ${JSON.stringify(context)}`;
}

/** Parses an SSE body into ADK events. Exported for tests. */
export function parseSseChunk(buffer: string): { events: AgentEvent[]; rest: string } {
  const events: AgentEvent[] = [];
  const blocks = buffer.split(/\r?\n\r?\n/);
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    const data = block
      .split(/\r?\n/)
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trimStart())
      .join("\n");
    if (data) events.push(JSON.parse(data) as AgentEvent);
  }
  return { events, rest };
}

/** One streamed chat turn (contracts §3). Resolves when the stream ends. */
export async function streamChat(opts: {
  question: string;
  context: ChatContext;
  onEvent: (e: AgentEvent) => void;
  signal?: AbortSignal;
}): Promise<void> {
  const { signal, done } = withTimeout(CHAT_TIMEOUT_MS, opts.signal);
  try {
    chatSession ??= createSession(signal).catch((e) => {
      chatSession = null;
      throw e;
    });
    const sessionId = await chatSession;
    const res = await fetch("/run_sse", {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal,
      body: JSON.stringify({
        app_name: APP,
        user_id: userId,
        session_id: sessionId,
        streaming: true,
        new_message: { role: "user", parts: [{ text: opts.question }, { text: contextPart(opts.context) }] },
      }),
    });
    if (!res.ok || !res.body) throw new Error(`The agent did not answer (HTTP ${res.status})`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done: finished } = await reader.read();
      buffer += decoder.decode(value, { stream: !finished });
      const parsed = parseSseChunk(finished ? buffer + "\n\n" : buffer);
      buffer = parsed.rest;
      for (const e of parsed.events) {
        if (e.errorCode || e.errorMessage) throw new Error(e.errorMessage ?? e.errorCode);
        opts.onEvent(e);
      }
      if (finished) break;
    }
  } catch (e) {
    if (signal.aborted && (signal.reason as DOMException)?.name === "TimeoutError") {
      throw new Error("The agent took longer than 90 seconds");
    }
    throw e;
  } finally {
    done();
  }
}
