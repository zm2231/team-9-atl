// Mock agent service for tests and VITE_MOCK_AGENT=1 (contracts/agent-interface.md).
import { http, HttpResponse } from "msw";
import mapData from "./mapData.fixture.json";

const APP = "readiness_agent";

const LIVE = "Macon Centreplex is open and listed on Google Maps as an event venue.";
const ANSWER =
  `Within reach of the affected counties, two receiving shelters stand out. ${LIVE} ` +
  "The registry records Macon Centreplex as wheelchair accessible (recorded yes). " +
  "Waycross Middle School has no wheelchair-access record: nobody has assessed it.";

export const mockGrounding = {
  groundingChunks: [
    { maps: { uri: "https://maps.google.com/?cid=1", title: "Macon Centreplex", placeId: "place-macon" } },
  ],
  groundingSupports: [
    {
      segment: { startIndex: ANSWER.indexOf(LIVE), endIndex: ANSWER.indexOf(LIVE) + LIVE.length, text: LIVE },
      groundingChunkIndices: [0],
    },
  ],
};

function sse(events: unknown[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

export const chatEvents = [
  {
    author: APP,
    content: {
      role: "model",
      // Same shape as the real get_shelters tool: shelter_record rows plus the source table.
      parts: [
        {
          functionResponse: {
            name: "get_shelters",
            response: {
              shelters: mapData.shelters.filter((s) => s.shelter_id === "M1" || s.shelter_id === "W1"),
              source: "FEMA NSS registry · shelters_clean",
            },
          },
        },
      ],
    },
  },
  {
    author: APP,
    content: {
      role: "model",
      parts: [
        {
          functionResponse: {
            name: "record_live_check",
            response: {
              live_check: { shelter_id: "M1", status: "exists", place_id: "place-macon", checked_at: "2026-10-27T16:00:00Z" },
            },
          },
        },
      ],
    },
  },
  { author: APP, partial: true, content: { role: "model", parts: [{ text: ANSWER.slice(0, 60) }] } },
  { author: APP, partial: true, content: { role: "model", parts: [{ text: ANSWER.slice(60) }] } },
  { author: APP, partial: false, content: { role: "model", parts: [{ text: ANSWER }] }, groundingMetadata: mockGrounding },
];

export const handlers = [
  http.post(`/apps/${APP}/users/:user/sessions`, () => HttpResponse.json({ id: `s-${Math.random().toString(36).slice(2)}` })),
  http.get("/map-data", () => HttpResponse.json(mapData)),
  http.post("/run_sse", () =>
    new HttpResponse(sse(chatEvents), { headers: { "content-type": "text/event-stream" } }),
  ),
];
