# Contract: History UI behaviour

This is the user-facing contract the e2e and component tests check. Names in `code` are test IDs
or accessible names.

## History section (top of the chat column; FR-006)

- **Header**: a button, `History (N) ▾/▸`, with `aria-expanded` and
  `aria-controls="history-list"`. It starts **collapsed**. N is the number of saved scenarios.
- **Expanded**: `<ul id="history-list">`, newest first by last opened (FR-011). Each entry:
  - is a button (`data-testid="history-item"`) showing the name, a `Cat N` badge, crossed
    counties (the first three plus "+N") and a relative last-opened time
  - has `aria-current="true"` and a highlight when it is the current scenario (FR-001a)
  - has "Rename" (an inline input; Enter saves, Esc cancels) and "Delete" (inline
    confirmation: `Delete '<name>'?` with Delete and Cancel buttons)
- **Footer note**: "Saved in this browser only" (FR-015). If storage is unavailable, it reads
  "History can't be saved in this browser".
- **Notice**: an eviction notice (FR-014) is shown once above the list and can be dismissed.

## Map controls (FR-001b, FR-001c)

- `Reset` is replaced by **`New simulation`**. It is enabled whenever a scenario is current, and
  it clears the map, the scenario lists and the chat.
- **Redraw hurricane track**, the category picker and the reach slider all update the
  **current** scenario. They never add an entry.

## Reopened scenario (FR-007 to FR-010)

- The map shows the saved track, category and cutoff, and every result is recomputed.
- `AffectedSummary` shows `Re-simulated at HH:MM from current data`
  (`data-testid="resimulated"`).
- The chat column shows **Earlier questions** (`data-testid="earlier-questions"`), one row per
  saved question, each with an **Ask again** button that sends it with this scenario's context.
- New questions are appended to this scenario.
