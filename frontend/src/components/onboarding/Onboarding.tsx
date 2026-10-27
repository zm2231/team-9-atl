import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { TOUR_STEPS } from "../../lib/onboarding";
import { useStore } from "../../state/store";

const GAP = 12;
const PAD = 6;
const EDGE = 2;
const PHONE = 600;

interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

function measure(selector: string | undefined): Box | null {
  const el = selector ? document.querySelector(selector) : null;
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  const left = Math.max(EDGE, r.left - PAD);
  const top = Math.max(EDGE, r.top - PAD);
  const right = Math.min(window.innerWidth - EDGE, r.right + PAD);
  const bottom = Math.min(window.innerHeight - EDGE, r.bottom + PAD);
  if (right <= left || bottom <= top) return null;
  return { top, left, width: right - left, height: bottom - top };
}

const sameBox = (a: Box | null, b: Box | null) =>
  a === b || (!!a && !!b && a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height);

function cardPosition(box: Box, card: { width: number; height: number }) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (vw <= PHONE) {
    const lowerHalf = box.top + box.height / 2 > vh / 2;
    return { top: lowerHalf ? GAP : vh - card.height - GAP, left: GAP };
  }
  const below = box.top + box.height + GAP;
  const above = box.top - GAP - card.height;
  const top =
    below + card.height <= vh - GAP ? below : above >= GAP ? above : Math.max(GAP, Math.min(box.top + GAP, vh - card.height - GAP));
  const left = Math.max(GAP, Math.min(box.left, vw - card.width - GAP));
  return { top, left };
}

export default function Onboarding({ onClose }: { onClose: () => void }) {
  const { dispatch } = useStore();
  const [index, setIndex] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const [cardSize, setCardSize] = useState({ width: 0, height: 0 });
  const cardRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const step = TOUR_STEPS[index];
  const last = index === TOUR_STEPS.length - 1;

  useEffect(() => {
    if (step.tab) dispatch({ type: "setSideTab", tab: step.tab });
    const frame = requestAnimationFrame(() => {
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      const el = step.target ? document.querySelector(step.target) : null;
      el?.scrollIntoView?.({ block: "center", behavior: reduce ? "auto" : "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [step, dispatch]);

  useEffect(() => {
    let frame = 0;
    const tick = () => {
      const next = measure(step.target);
      setBox((prev) => (sameBox(prev, next) ? prev : next));
      const card = cardRef.current;
      if (card) {
        const { offsetWidth: width, offsetHeight: height } = card;
        setCardSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
      }
      frame = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frame);
  }, [step]);

  useLayoutEffect(() => {
    nextRef.current?.focus();
  }, [index]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab" || !cardRef.current) return;
    const items = [...cardRef.current.querySelectorAll<HTMLElement>("button:not([disabled])")];
    if (items.length === 0) return;
    const first = items[0];
    const end = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      end.focus();
    } else if (!e.shiftKey && document.activeElement === end) {
      e.preventDefault();
      first.focus();
    }
  };

  const placed = box && cardSize.height > 0 ? cardPosition(box, cardSize) : null;

  return (
    <div
      className="tour"
      onKeyDown={onKeyDown}
      onMouseDown={(e) => {
        if (!cardRef.current?.contains(e.target as Node)) e.preventDefault();
      }}
    >
      {box ? (
        <div className="tour__spot" style={box} aria-hidden="true" />
      ) : (
        <div className="tour__backdrop" aria-hidden="true" />
      )}
      <div
        ref={cardRef}
        className={`tour__card${placed ? "" : " tour__card--center"}`}
        style={placed ?? undefined}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
      >
        <p className="tour__count muted small">
          Step {index + 1} of {TOUR_STEPS.length}
        </p>
        <h2 id="tour-title">{step.title}</h2>
        <p id="tour-body">{step.body}</p>
        <div className="tour__actions">
          {!last && (
            <button type="button" className="link-btn" onClick={onClose}>
              Skip
            </button>
          )}
          <span className="tour__nav">
            <button type="button" className="btn" disabled={index === 0} onClick={() => setIndex(index - 1)}>
              Back
            </button>
            <button
              ref={nextRef}
              type="button"
              className="btn btn--primary"
              onClick={() => (last ? onClose() : setIndex(index + 1))}
            >
              {last ? "Done" : "Next"}
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}
