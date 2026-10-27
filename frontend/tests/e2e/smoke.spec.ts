// SC-007 demo path against the MSW-mocked agent (VITE_MOCK_AGENT=1, see playwright.config.ts).
import { expect, test } from "@playwright/test";

test("demo path: map → hover → hurricane → receiving list → grounded answer", async ({ page }) => {
  await page.goto("/");

  // 1. County outlines, then shelters.
  await expect(page.locator("path.county")).toHaveCount(159);
  await expect(page.locator("circle.shelter").first()).toBeVisible({ timeout: 20_000 });

  // 2. Focus a county (keyboard path; same handler as hover) → summary with all three counts.
  await page.locator('path.county[data-fips="13157"]').focus();
  const summary = page.getByTestId("county-summary");
  await expect(summary).toContainText("Jackson County");
  await expect(summary).toContainText("Excludes 2 shelters with suspect capacity");
  await expect(summary).toContainText("not recorded");

  // 3. Draw a track across Glynn and inland; Category 3 is the default.
  await page.getByRole("button", { name: "Draw hurricane track" }).click();
  const box = (await page.getByTestId("draw-overlay").boundingBox())!;
  const glynn = (await page.locator('path.county[data-fips="13127"]').boundingBox())!;
  const start = { x: Math.min(box.x + box.width - 5, glynn.x + glynn.width + 60), y: glynn.y + glynn.height / 2 };
  const end = { x: glynn.x - 120, y: glynn.y - 40 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(start.x + ((end.x - start.x) * i) / 10, start.y + ((end.y - start.y) * i) / 10);
  }
  await page.mouse.up();

  // 4. Affected summary and receiving list, labeled straight-line with the 80 km cutoff.
  await expect(page.getByTestId("affected-summary")).toContainText("Category 3");
  await expect(page.getByTestId("affected-summary")).toContainText("Illustrative scenario — not a forecast");
  await expect(page.getByText("Within reach:")).toContainText("80 km");
  await expect(page.getByTestId("receiving-list")).toContainText("Straight-line distance");

  // 5–6. Ask; sources appear under the live segment and the referenced shelter is highlighted.
  await page.getByLabel("Question for the agent").fill("Which of these receiving shelters can actually take a wheelchair?");
  await page.getByRole("button", { name: "Send" }).click();
  const answer = page.getByTestId("answer").last();
  await expect(answer.getByTestId("sources")).toContainText("Google Maps");
  await expect(answer.locator('[translate="no"]')).toHaveText("Google Maps");
  await expect(page.locator('[data-shelter-id="M1"] circle.shelter--highlight')).toHaveCount(1);
});
