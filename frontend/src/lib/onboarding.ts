export const ONBOARDING_KEY = "gsr.onboarding.v1";

export interface TourStep {
  title: string;
  body: string;
  target?: string;
  tab?: "chat" | "details";
}

export const TOUR_STEPS: TourStep[] = [
  {
    title: "Plan before the season",
    body: "A planning tool for county emergency managers to check shelter readiness before hurricane season. It is not for live operations.",
    target: ".topbar h1",
  },
  {
    title: "Move around and pick a county",
    body: "Drag to pan; scroll, pinch or use + and − to zoom, and ⟲ to reset. Click a county to open Details: who can't leave, the shelters nearby and the gaps.",
    target: ".map",
  },
  {
    title: "Draw a hurricane track",
    body: "Click Draw hurricane track, then press and drag across the map along the storm's path. Let go to finish; the storm is simulated at once. Redraw to replace it.",
    target: ".controls > .btn",
  },
  {
    title: "Set category and reach",
    body: "Pick Cat 1 to 5 and set Within reach. Counties shade by modelled power outage. New simulation starts over; the old one stays in History.",
    target: ".controls",
  },
  {
    title: "Ask the agent",
    body: "Try \"Give me Chatham County's readiness plan\" or \"Show the state season outlook\". Answers cite their sources and check shelters live on Google Maps.",
    target: ".chat__form",
    tab: "chat",
  },
  {
    title: "Reports and history",
    body: "Reports open in the chat; Expand reads them full screen. History keeps every scenario you run, and opening one restores the storm and its conversation. Drag the panel's left edge to resize it.",
    target: ".history",
    tab: "chat",
  },
];

export function shouldShowOnboarding(storage: Pick<Storage, "getItem"> | null): boolean {
  if (!storage) return true;
  try {
    return storage.getItem(ONBOARDING_KEY) === null;
  } catch {
    return true;
  }
}

export function markOnboardingSeen(storage: Pick<Storage, "setItem"> | null): void {
  try {
    storage?.setItem(ONBOARDING_KEY, "done");
  } catch {
    return;
  }
}
