import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { StoreProvider } from "./state/store";
import "./styles/app.css";
import "./styles/flags.css";

async function start() {
  // Mock agent for demos and the e2e smoke test (VITE_MOCK_AGENT=1). Never part of a normal build.
  if (import.meta.env.VITE_MOCK_AGENT) {
    const { setupWorker } = await import("msw/browser");
    const { handlers } = await import("../tests/mocks/handlers");
    await setupWorker(...handlers).start({ onUnhandledRequest: "bypass" });
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <StoreProvider>
        <App />
      </StoreProvider>
    </StrictMode>,
  );
}

void start();
