# Quickstart: Scenario History

This is frontend-only, so run the app as in
[001 quickstart](../001-georgia-shelter-map/quickstart.md). Either use mock mode
(`cd frontend && VITE_MOCK_AGENT=1 npm run dev`), or use the real agent on :8000 with
`npm run dev`.

## Tests

```bash
cd frontend
npx vitest run                       # history.test.ts, historyReducer.test.ts, HistorySection.test.tsx
npx playwright test tests/e2e/history.spec.ts
```

## Manual walk-through (spec acceptance)

1. Draw a Category 3 track across Glynn. Open **History** in the chat column: one entry,
   "Cat 3 · Glynn → …", highlighted as current.
2. Ask "Which of these receiving shelters can actually take a wheelchair?".
3. **Reload the page.** History still lists the scenario and its question (SC-007).
4. Change the category to 4 and the cutoff to 120 km. There is still one entry, and its name
   updates (FR-001c, R5).
5. Press **New simulation**. The map and chat clear, and the entry remains (FR-001b).
6. Draw a second track across Chatham. History now has two entries, and the new one is current.
7. Click the first entry. The track shows with Category 4 and 120 km, "Re-simulated at …" appears,
   and the receiving list is recomputed. **Earlier questions** lists the wheelchair question;
   **Ask again** gets a fresh answer (FR-007 to FR-009).
8. Rename the first entry to "Glynn worst case". Delete the second and confirm.
9. In DevTools, open Application → Local Storage → `gsr.scenarioHistory.v1`. Confirm it holds only
   tracks, settings, names and question text, with no answers and no "Google Maps" content
   (SC-005).
