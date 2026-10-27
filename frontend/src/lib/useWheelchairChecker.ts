import { useCallback, useState } from "react";
import { useStore } from "../state/store";
import { checkWheelchair } from "./agentClient";

/** Ids already sent this session, so list and detail views never ask Maps twice for one shelter. */
const attempted = new Set<string>();

/** Live Google Maps wheelchair lookups for shelters with a blank registry record. */
export function useWheelchairChecker() {
  const { state, dispatch } = useStore();
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string>();

  const run = useCallback(
    async (ids: string[]) => {
      setPending((n) => n + 1);
      setError(undefined);
      try {
        dispatch({ type: "wheelchairChecked", results: await checkWheelchair(ids) });
      } catch (e) {
        ids.forEach((id) => attempted.delete(id)); // a failed lookup may be retried
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setPending((n) => n - 1);
      }
    },
    [dispatch],
  );

  /** Checks only ids never sent before; used for the automatic lookups. */
  const checkOnce = useCallback(
    (ids: string[]) => {
      const fresh = ids.filter((id) => !attempted.has(id) && !state.wheelchairChecks.has(id));
      if (fresh.length === 0) return;
      fresh.forEach((id) => attempted.add(id));
      void run(fresh);
    },
    [run, state.wheelchairChecks],
  );

  return { checks: state.wheelchairChecks, checking: pending > 0, error, check: run, checkOnce };
}
