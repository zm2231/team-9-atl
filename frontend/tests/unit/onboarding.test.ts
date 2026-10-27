import { describe, expect, it } from "vitest";
import { ONBOARDING_KEY, TOUR_STEPS, markOnboardingSeen, shouldShowOnboarding } from "../../src/lib/onboarding";

function fakeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

const throwing = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
};

describe("onboarding show-once", () => {
  it("shows on a first visit", () => {
    expect(shouldShowOnboarding(fakeStorage())).toBe(true);
  });

  it("stays hidden once dismissed", () => {
    const storage = fakeStorage();
    markOnboardingSeen(storage);
    expect(storage.data.get(ONBOARDING_KEY)).toBe("done");
    expect(shouldShowOnboarding(storage)).toBe(false);
  });

  it("uses the versioned key", () => {
    expect(ONBOARDING_KEY).toBe("gsr.onboarding.v1");
    expect(shouldShowOnboarding(fakeStorage({ "gsr.onboarding.v0": "done" }))).toBe(true);
  });

  it("shows when storage is missing or blocked, and dismissing never throws", () => {
    expect(shouldShowOnboarding(null)).toBe(true);
    expect(shouldShowOnboarding(throwing)).toBe(true);
    expect(() => markOnboardingSeen(throwing)).not.toThrow();
    expect(() => markOnboardingSeen(null)).not.toThrow();
  });

  it("points every step but the first at a control", () => {
    expect(TOUR_STEPS.slice(1).every((s) => s.target)).toBe(true);
  });
});
