import { afterEach, describe, expect, it, vi } from "vitest";
import { parseSseChunk, resetChatSession, streamChat, type AgentEvent } from "../../src/lib/agentClient";

const ERROR_EVENT = { error: "ValueError: boom", error_details: { error_type: "ValueError", error_message: "boom" } };

function sseResponse(events: unknown[]): Response {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("parseSseChunk", () => {
  it("parses ADK's mid-stream error event", () => {
    const { events, rest } = parseSseChunk(`data: ${JSON.stringify(ERROR_EVENT)}\n\n`);
    expect(rest).toBe("");
    expect(events[0].error).toBe("ValueError: boom");
  });
});

describe("streamChat", () => {
  it("rejects when the stream ends with an error event (FR-015)", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("/sessions")
        ? new Response(JSON.stringify({ id: "s1" }), { status: 200 })
        : sseResponse([{ author: "readiness_agent", partial: true, content: { parts: [{ text: "Partial" }] } }, ERROR_EVENT]),
    );
    vi.stubGlobal("fetch", fetchMock);
    const seen: AgentEvent[] = [];
    await expect(
      streamChat({
        question: "q",
        context: { county_fips: null, shelter_id: null, scenario: null },
        onEvent: (e) => seen.push(e),
      }),
    ).rejects.toThrow("ValueError: boom");
    expect(seen).toHaveLength(1);
  });
});

describe("resuming a saved scenario's session", () => {
  const ask = (onSession: (id: string) => void) =>
    streamChat({
      question: "q",
      context: { county_fips: null, shelter_id: null, scenario: null },
      onEvent: () => {},
      onSession,
    });
  const ok = () => sseResponse([{ author: "readiness_agent", content: { parts: [{ text: "hi" }] } }]);

  it("sends the question to the saved session", async () => {
    const bodies: { session_id: string; user_id: string }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/sessions")) return new Response(JSON.stringify({ id: "fresh" }), { status: 200 });
      bodies.push(JSON.parse(String(init?.body)));
      return ok();
    }));
    resetChatSession("saved-1");
    const used: string[] = [];
    await ask((id) => used.push(id));
    expect(bodies.map((b) => b.session_id)).toEqual(["saved-1"]);
    expect(used).toEqual(["saved-1"]);
  });

  it("falls back to a fresh session when the saved one is gone", async () => {
    const sent: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/sessions")) return new Response(JSON.stringify({ id: "fresh" }), { status: 200 });
      const id = JSON.parse(String(init?.body)).session_id;
      sent.push(id);
      return id === "expired" ? new Response("gone", { status: 500 }) : ok();
    }));
    resetChatSession("expired");
    const used: string[] = [];
    await ask((id) => used.push(id));
    expect(sent).toEqual(["expired", "fresh"]);
    expect(used).toEqual(["fresh"]);
  });
});

describe("sessions created on this page", () => {
  it("surfaces an error for a session this page created instead of switching sessions", async () => {
    const sent: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/sessions")) return new Response(JSON.stringify({ id: "mine" }), { status: 200 });
      sent.push(JSON.parse(String(init?.body)).session_id);
      return new Response("boom", { status: 500 });
    }));
    resetChatSession();
    await expect(
      streamChat({ question: "q", context: { county_fips: null, shelter_id: null, scenario: null }, onEvent: () => {} }),
    ).rejects.toThrow("HTTP 500");
    expect(sent).toEqual(["mine"]);
  });
});
