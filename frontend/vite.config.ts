/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const AGENT = process.env.AGENT_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  // The MSW worker is only served in mock mode, so it never ships in a production build.
  publicDir: process.env.VITE_MOCK_AGENT ? "mock-public" : false,
  server: {
    // The agent service serves these routes in production from the same origin (research R1).
    proxy: {
      "/apps": AGENT,
      "/run": AGENT, // also matches /run_sse
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.ts", "tests/component/**/*.test.tsx"],
  },
});
