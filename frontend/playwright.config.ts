import { defineConfig, devices } from "@playwright/test";

// The e2e smoke test runs the app in mock mode: VITE_MOCK_AGENT=1 starts the MSW browser worker,
// so no agent service is needed (tasks T005, T050).
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:5173" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "VITE_MOCK_AGENT=1 npm run dev -- --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});
