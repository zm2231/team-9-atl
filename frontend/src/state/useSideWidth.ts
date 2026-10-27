import { useCallback, useEffect, useState } from "react";
import { MIN_SIDE, clampSideWidth, loadSideWidth, saveSideWidth } from "../lib/sideWidth";
import { browserStorage } from "./store";

export function useSideWidth() {
  const [chosen, setChosen] = useState(() => loadSideWidth(browserStorage()));
  const [viewport, setViewport] = useState(() => window.innerWidth);

  useEffect(() => {
    const onResize = () => setViewport(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const resize = useCallback((width: number, persist: boolean) => {
    const next = clampSideWidth(width, window.innerWidth);
    setChosen(next);
    if (persist) saveSideWidth(browserStorage(), next);
  }, []);

  return {
    width: clampSideWidth(chosen ?? viewport / 2, viewport),
    min: MIN_SIDE,
    max: clampSideWidth(Infinity, viewport),
    resize,
  };
}
