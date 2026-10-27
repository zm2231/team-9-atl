// Feature 002 scenario history, against the MSW-mocked agent (T013, T019).
import { expect, test, type Page } from "@playwright/test";

const KEY = "gsr.scenarioHistory.v1";

async function ready(page: Page) {
  await expect(page.locator("circle.shelter").first()).toBeVisible({ timeout: 20_000 });
}

/** Drags across a county, from just east of it to beyond its west edge. */
async function drawAcross(page: Page, fips: string) {
  await page.getByRole("button", { name: /Draw hurricane track|Redraw hurricane track/ }).click();
  const box = (await page.getByTestId("draw-overlay").boundingBox())!;
  const c = (await page.locator(`path.county[data-fips="${fips}"]`).boundingBox())!;
  const start = { x: Math.min(box.x + box.width - 5, c.x + c.width + 60), y: c.y + c.height / 2 };
  const end = { x: c.x - 120, y: c.y - 40 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(start.x + ((end.x - start.x) * i) / 10, start.y + ((end.y - start.y) * i) / 10);
  }
  await page.mouse.up();
  await expect(page.locator("path.band")).toHaveCount(1);
}

async function ask(page: Page, q: string) {
  await page.getByLabel("Question for the agent").fill(q);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("sources").last()).toContainText("Google Maps");
}

async function openHistory(page: Page) {
  const header = page.getByRole("button", { name: /^History \(\d+\)/ });
  if ((await header.getAttribute("aria-expanded")) !== "true") await header.click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate((k) => localStorage.removeItem(k), KEY);
  await page.reload();
  await ready(page);
});

test("survives reload and New simulation (T013, SC-005, SC-007)", async ({ page }) => {
  const QUESTION = "Which of these receiving shelters can actually take a wheelchair?";
  await drawAcross(page, "13127");
  await openHistory(page);
  const items = page.getByTestId("history-item");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toHaveAttribute("aria-current", "true");
  await expect(items.first()).toContainText("Cat 3 ·");

  await ask(page, QUESTION);

  await page.reload();
  await ready(page);
  await openHistory(page);
  await expect(page.getByTestId("history-item")).toHaveCount(1);

  const stored = await page.evaluate((k) => localStorage.getItem(k) ?? "", KEY);
  expect(stored).toContain(QUESTION);
  expect(stored).not.toContain("Google Maps");
  expect(stored).not.toContain("groundingMetadata");

  // After a reload nothing is current; reopen it, then start a new simulation.
  await page.getByTestId("history-item").first().click();
  await expect(page.locator("path.band")).toHaveCount(1);
  await page.getByRole("button", { name: "New simulation" }).click();
  await expect(page.locator("path.band")).toHaveCount(0);
  await expect(page.getByTestId("history-item")).toHaveCount(1);
  await expect(page.getByTestId("history-item").first()).not.toHaveAttribute("aria-current", "true");
});

test("reopen restores inputs and re-simulates (T019, SC-002, FR-007–FR-009)", async ({ page }) => {
  const QUESTION = "Which of these receiving shelters can actually take a wheelchair?";
  await drawAcross(page, "13127");
  await page.getByRole("button", { name: "Cat 4", exact: true }).click();
  await page.getByLabel("Within reach cutoff in miles").fill("75");
  await ask(page, QUESTION);

  await page.getByRole("button", { name: "New simulation" }).click();
  await drawAcross(page, "13051");
  await openHistory(page);
  await expect(page.getByTestId("history-item")).toHaveCount(2);

  // The older scenario is second (newest first).
  await page.getByTestId("history-item").nth(1).click();
  await expect(page.getByRole("button", { name: "Cat 4", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Within reach:")).toContainText("75 mi");
  await expect(page.locator("path.band")).toHaveCount(1);

  // Visible without opening Details (analysis M2), and inside Details (FR-008).
  await expect(page.getByTestId("resimulated-note")).toContainText("re-simulated at");
  await page.getByRole("tab", { name: /^Details/ }).click();
  await expect(page.getByTestId("resimulated")).toContainText("from current data");
  await page.getByRole("tab", { name: "Chat" }).click();

  const earlier = page.getByTestId("earlier-questions");
  await expect(earlier).toContainText(QUESTION);
  await earlier.getByRole("button", { name: "Ask again" }).click();
  await expect(page.getByTestId("answer").last().getByTestId("sources")).toContainText("Google Maps");
  // Re-asking adds to this scenario's saved questions and keeps the list available (FR-010, H2).
  await expect(earlier.getByRole("button", { name: "Ask again" })).toHaveCount(2);
});
