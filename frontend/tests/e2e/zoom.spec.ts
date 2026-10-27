// Feature 003 US3: zoom buttons, wheel/pinch about the pointer, drag to pan (FR-015–FR-021).
import { expect, test, type Page } from "@playwright/test";

// The legend draws sample dots with the same class, so map dots are always scoped to .map.
const MAP_DOT = ".map circle.shelter";
const svg = (page: Page) => page.locator(".map svg");
const k = async (page: Page) => Number(await svg(page).getAttribute("data-zoom-k"));
const layerTransform = (page: Page) => page.locator("g.zoom-layer").getAttribute("transform");
const zoomIn = (page: Page) => page.getByRole("button", { name: "Zoom in" });
const zoomOut = (page: Page) => page.getByRole("button", { name: "Zoom out" });
const reset = (page: Page) => page.getByRole("button", { name: "Reset view" });

async function centre(page: Page, selector: string) {
  const b = (await page.locator(selector).first().boundingBox())!;
  return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width };
}

async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(from.x + ((to.x - from.x) * i) / 10, from.y + ((to.y - from.y) * i) / 10);
  }
  await page.mouse.up();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem("gsr.onboarding.v1", "done");
  });
  await page.reload();
  await expect(page.locator(MAP_DOT).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("status")).toHaveCount(0);
});

test("buttons step 1.5× and stop at the whole state and at 8×", async ({ page }) => {
  await expect(zoomOut(page)).toBeDisabled();
  await expect(reset(page)).toBeDisabled();
  await expect(zoomIn(page)).toBeEnabled();
  expect(await k(page)).toBe(1);

  await zoomIn(page).click();
  await expect.poll(() => k(page)).toBeCloseTo(1.5, 5);
  await expect(zoomOut(page)).toBeEnabled();

  while (await zoomIn(page).isEnabled()) await zoomIn(page).click();
  expect(await k(page)).toBe(8);

  await reset(page).click();
  await expect.poll(() => k(page)).toBe(1);
  await expect(zoomOut(page)).toBeDisabled();
});

test("wheel zooms about the pointer, stops at its limit and never scrolls the page", async ({ page }) => {
  const dot = await centre(page, MAP_DOT);
  await page.mouse.move(dot.x, dot.y);
  const scrollY = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, -400);
  await expect.poll(() => k(page)).toBeGreaterThan(1);
  const after = await centre(page, MAP_DOT);
  expect(Math.abs(after.x - dot.x)).toBeLessThan(3);
  expect(Math.abs(after.y - dot.y)).toBeLessThan(3);

  for (let i = 0; i < 10; i++) await page.mouse.wheel(0, -800);
  await expect.poll(() => k(page)).toBe(8);
  await page.mouse.wheel(0, -800);
  expect(await k(page)).toBe(8);
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollY);
});

test("double-click does not zoom", async ({ page }) => {
  const box = (await svg(page).boundingBox())!;
  await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2);
  expect(await k(page)).toBe(1);
});

test("dragging pans when zoomed in, without selecting what it ends on", async ({ page }) => {
  await zoomIn(page).click();
  await zoomIn(page).click();
  const before = await layerTransform(page);
  const box = (await svg(page).boundingBox())!;
  const from = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await drag(page, from, { x: from.x + 100, y: from.y + 60 });
  await expect.poll(() => layerTransform(page)).not.toBe(before);
  await expect(page.locator("path.county--selected")).toHaveCount(0);
});

test("markers keep their on-screen size", async ({ page }) => {
  const at1 = await centre(page, MAP_DOT);
  for (let i = 0; i < 4; i++) await zoomIn(page).click();
  await expect.poll(() => k(page)).toBeGreaterThan(4);
  const at5 = await centre(page, MAP_DOT);
  expect(Math.abs(at5.w - at1.w)).toBeLessThan(1);
});

test("a track drawn while zoomed lands under the pointer", async ({ page }) => {
  await zoomIn(page).click();
  await expect.poll(() => k(page)).toBeCloseTo(1.5, 5);
  // Drawing re-labels and adds buttons that can re-flow the map, so measure against map dots,
  // which move with it, after drawing mode is on.
  await page.getByRole("button", { name: "Draw hurricane track" }).click();
  const box = (await svg(page).boundingBox())!;
  const dots = page.locator(MAP_DOT);
  const inView: { i: number; x: number; y: number }[] = [];
  for (let i = 0; i < (await dots.count()); i++) {
    const b = await dots.nth(i).boundingBox();
    if (!b) continue;
    const c = { i, x: b.x + b.width / 2, y: b.y + b.height / 2 };
    if (c.x > box.x + 20 && c.x < box.x + box.width - 60 && c.y > box.y + 20 && c.y < box.y + box.height - 20) inView.push(c);
  }
  inView.sort((p, q) => p.x - q.x);
  const [from, to] = [inView[inView.length - 1], inView[0]];
  expect(Math.abs(from.x - to.x)).toBeGreaterThan(80);

  await drag(page, from, to);
  await expect(page.locator("path.band")).toHaveCount(1);

  const at = async (i: number) => {
    const b = (await dots.nth(i).boundingBox())!;
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  };
  const [a, b] = [await at(from.i), await at(to.i)];
  const track = (await page.locator("path.track").first().boundingBox())!;
  // Chromium's box includes the stroke, so allow a few pixels on each edge.
  expect(Math.abs(track.x - Math.min(a.x, b.x))).toBeLessThan(7);
  expect(Math.abs(track.x + track.width - Math.max(a.x, b.x))).toBeLessThan(7);
  expect(Math.abs(track.y - Math.min(a.y, b.y))).toBeLessThan(7);
  expect(Math.abs(track.y + track.height - Math.max(a.y, b.y))).toBeLessThan(7);
});

test("reopening a saved scenario starts at the whole state", async ({ page }) => {
  await page.getByRole("button", { name: "Draw hurricane track" }).click();
  const box = (await page.getByTestId("draw-overlay").boundingBox())!;
  await drag(page, { x: box.x + box.width * 0.8, y: box.y + box.height * 0.8 }, { x: box.x + box.width * 0.5, y: box.y + box.height * 0.6 });
  await expect(page.locator("path.band")).toHaveCount(1);
  await page.getByRole("button", { name: "New simulation" }).click();

  await zoomIn(page).click();
  await expect.poll(() => k(page)).toBeGreaterThan(1);
  const header = page.getByRole("button", { name: /^History \(\d+\)/ });
  if ((await header.getAttribute("aria-expanded")) !== "true") await header.click();
  await page.getByTestId("history-item").first().click();
  await expect.poll(() => k(page)).toBe(1);
});
