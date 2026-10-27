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
    title: "Pick a county",
    body: "Click a county on the map. The Details pane shows who can't leave, the shelters nearby and the gaps.",
    target: ".map",
  },
  {
    title: "Simulate a storm",
    body: "Draw a hurricane track across the map, then pick a category. Counties shade by modelled power outage.",
    target: ".controls",
  },
  {
    title: "Ask the agent",
    body: "Try \"Give me Chatham County's readiness plan\" or \"Show the state season outlook\". Answers cite their sources and check shelters live on Google Maps.",
    target: ".chat__form",
    tab: "chat",
  },
  {
    title: "Come back to a scenario",
    body: "History keeps every scenario you run. Opening one restores the storm and its conversation.",
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
