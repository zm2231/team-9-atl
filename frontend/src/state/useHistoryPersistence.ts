import { useEffect, useRef } from "react";
import { STORAGE_KEY, loadHistory, saveHistory } from "../lib/history";
import { useStore } from "./store";

function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/**
 * The only code that touches localStorage (feature 002, research R1/R2). Loads once, then writes
 * the whole history after every change, synchronously, so a reload never loses the last change.
 */
export function useHistoryPersistence(): void {
  const { state, dispatch } = useStore();
  const storage = useRef<Storage | null>(null);
  const skipNextSave = useRef(true);

  useEffect(() => {
    storage.current = browserStorage();
    const loaded = loadHistory(storage.current);
    if (loaded.unreadable && storage.current) {
      // Never silently overwrite a document we could not read: keep a copy first (analysis H1).
      try {
        const raw = storage.current.getItem(STORAGE_KEY);
        if (raw !== null && storage.current.getItem(`${STORAGE_KEY}.bak`) === null) {
          storage.current.setItem(`${STORAGE_KEY}.bak`, raw);
        }
      } catch {
        // Storage became unavailable; saving below will report it.
      }
    }
    dispatch({ type: "historyLoaded", scenarios: loaded.scenarios, available: loaded.available });
  }, [dispatch]);

  useEffect(() => {
    if (!state.historyLoaded) return;
    if (skipNextSave.current) {
      // The first run is the load itself; nothing has changed yet.
      skipNextSave.current = false;
      return;
    }
    if (!saveHistory(storage.current, state.history) && state.historyAvailable) {
      dispatch({ type: "historyUnavailable" });
    }
  }, [state.history, state.historyLoaded, state.historyAvailable, dispatch]);
}
