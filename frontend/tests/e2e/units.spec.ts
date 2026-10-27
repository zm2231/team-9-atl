// Feature 003 US1: miles by default, a km toggle, remembered in this browser (FR-001–FR-007a).
import { expect, test, type Page } from "@playwright/test";

const UNIT_KEY = "gsr.distanceUnit.v1";

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

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate((k) => localStorage.removeItem(k), UNIT_KEY);
  await page.reload();
  await expect(page.locator("circle.shelter").first()).toBeVisible({ timeout: 20_000 });
});

test("miles first, km on toggle with identical results, remembered after reload", async ({ page }) => {
  const units = page.getByRole("radiogroup", { name: "Distance unit" });
  await expect(units.getByRole("radio", { name: "Miles" })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByText("Within reach:")).toContainText("50 mi");

  await drawAcross(page, "13127");
  await page.getByRole("tab", { name: /^Details/ }).click();
  const affected = page.getByTestId("affected-summary");
  await expect(affected).toContainText("mi either side");
  const rows = page.getByTestId("receiving-row");
  const count = await rows.count();
  const counties = await affected.textContent();

  await units.getByRole("radio", { name: "Kilometres" }).click();
  await expect(page.getByText("Within reach:")).toContainText("80 km");
  await expect(affected).toContainText("km either side");
  await expect(rows).toHaveCount(count);
  expect((await affected.textContent())?.replace(/\d+ km/, "")).toBe(counties?.replace(/\d+ mi/, ""));

  await page.reload();
  await expect(page.getByRole("radio", { name: "Kilometres" })).toHaveAttribute("aria-checked", "true");
  expect(await page.evaluate((k) => localStorage.getItem(k), UNIT_KEY)).toBe("km");
});
