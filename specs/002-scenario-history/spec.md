# Feature Specification: Scenario History

**Feature Branch**: `002-scenario-history`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Track past simulation sessions. The user draws a line, asks questions, and is ready to draw another simulation; save that previous session. Like chat history in Claude: the user sees a list and clicks a previous session. Save the line that was drawn, but the results should be re-simulated."

## Readiness Scenario & Data Honesty *(mandatory)*

**Scenario**: Our agent helps a **county emergency manager** in **Georgia** **compare and revisit the hurricane scenarios they have already explored** before **the peak of hurricane season (September)**, without redrawing them from memory.
**Track / State**: Shelter Readiness / Georgia (GA), building on feature 001 (Georgia Shelter Readiness Map).
**Brief segments served**:
- Where they would go and whether that holds up
- What to fix before the season, by revisiting earlier scenarios against current data
- What we could not tell you, shown again for each reopened scenario
**Unrecorded handling**: Reopened scenarios show the same Yes / No / Not recorded counts as a fresh one. Nothing is cached, so a shelter that was "Not recorded" last week and has since been assessed shows its current status.
**World vs paperwork**: Only the user's own inputs are saved: the drawn track, the category, the reach cutoff and the questions asked. Registry figures, live checks and simulation results are never saved. They are produced again from current data when a scenario is reopened, so a saved scenario cannot show a stale figure as current.
**What we could not tell you**: A reopened scenario cannot show how its results looked when it was first run. Only current results are shown, so the user cannot see what changed between then and now.

## Clarifications

### Session 2026-10-27

- Q: Who can see saved scenarios? → A: This browser on this device only.
- Q: What gets saved from the chat? → A: The question text only. Answers are never saved; reopening lists the questions and re-asking gets a fresh answer.
- Q: When is a scenario saved? → A: Continuously. It appears in the list as soon as a track is drawn, every change is saved immediately, and the current scenario is highlighted in the list.
- Q: What starts a new scenario? → A: A dedicated "New simulation" button, which replaces Reset. Redraw replaces the track in the current scenario; the current scenario stays saved when a new one starts.
- Q: Where does the history list live? → A: A collapsible "History" section at the top of the chat column, listing scenarios above the conversation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep a scenario when starting a new one (Priority: P1)

The planner draws a Category 3 track across Glynn County, reviews the affected and receiving shelters, and asks the agent a couple of questions. They then want to try a different track. The scenario has been saved to the history list since the moment the track was drawn, so starting a new simulation, reloading the page or closing the tab loses nothing.

**Why this priority**: Without it, every new drawing silently discards the previous one. This is the core of the request.

**Independent Test**: Draw a track and ask one question. Reload the page and check that the scenario and its question are still listed. Then start a new simulation and check that the earlier scenario is still listed and the map is clear for the new drawing.

**Acceptance Scenarios**:

1. **Given** a drawn track with at least one question asked, **When** the user presses New simulation, **Then** the previous scenario stays in the history list, and the map, scenario lists and chat are cleared for the new one.
2. **Given** a track has just been drawn, **When** the drag ends, **Then** the scenario appears at the top of the history list, highlighted as current.
3. **Given** a scenario in progress, **When** the user reloads the page or closes and reopens the tab, **Then** the scenario and its questions are still in the history list.
4. **Given** a drawn track with no questions asked, **When** the user presses New simulation, **Then** the scenario is still saved, because the drawing alone is worth keeping.
5. **Given** the user has pressed New simulation, **When** they have not yet drawn a track, **Then** no empty entry is added to the history.
6. **Given** a scenario in progress, **When** the user changes its category or reach cutoff, or redraws its track, **Then** the change belongs to the same scenario and no new entry is created.

---

### User Story 2 - Reopen a past scenario and see current results (Priority: P1)

The planner opens the history list and clicks a scenario from earlier. The map redraws the same track with the same category and reach cutoff. The affected counties and shelters, the receiving list and the summaries are worked out again from current data, not shown from a saved copy. The earlier questions are shown so the planner can see what was asked.

**Why this priority**: Saving is useless without reopening, and re-simulating is what the user explicitly asked for.

**Independent Test**: Save a scenario, start another, then reopen the first. Check that the track, category and cutoff match what was drawn, and that the lists are produced again. Re-simulating an unchanged scenario against the same data gives identical lists.

**Acceptance Scenarios**:

1. **Given** a saved scenario, **When** the user selects it in the History section of the chat column, **Then** the map shows its track, category and reach cutoff, and its affected summary and receiving list are recomputed from the current shelter data.
2. **Given** a saved scenario reopened after the shelter data changed (e.g. a shelter's wheelchair access was assessed), **When** its results are shown, **Then** they reflect the current data, and the screen says the results were re-simulated (when) rather than restored.
3. **Given** a reopened scenario, **When** the user asks a new question, **Then** the question goes to the agent with this scenario's context and is added to this scenario's history.
4. **Given** a reopened scenario whose earlier questions are listed, **When** the user wants an earlier answer again, **Then** they can re-ask that question with one action and get a fresh answer.
5. **Given** the user is in the middle of a scenario, **When** they open a different saved scenario, **Then** the current one is already saved (FR-001) and becomes an ordinary entry in the list.

---

### User Story 3 - Manage the history list (Priority: P2)

The planner sees the list newest first, with names that make scenarios easy to tell apart. They can rename a scenario and delete ones they no longer need.

**Why this priority**: A long, unlabeled list quickly becomes useless. Renaming and deleting keep it usable, but the feature works without them.

**Independent Test**: Create three scenarios, rename one, delete another, and check the list order, names and count.

**Acceptance Scenarios**:

1. **Given** saved scenarios, **When** the list is shown, **Then** entries are newest first. Each shows a name, its category, the counties the track crosses (abbreviated if many) and when it was last opened.
2. **Given** a new scenario, **When** it is saved, **Then** it gets a default name built from its category and the first and last county the track crosses (e.g. "Cat 3 · Glynn → Ware").
3. **Given** a saved scenario, **When** the user renames it, **Then** the new name is shown everywhere the scenario appears.
4. **Given** a saved scenario, **When** the user deletes it and confirms, **Then** it is removed from the list and cannot be reopened.

---

### Edge Cases

- **Track no longer fits the data**: a saved track no longer affects any Georgia county or shelter with current data. It reopens with the usual empty-state messages, not an error.
- **Shelter missing from current data**: a scenario's earlier question referred to a shelter that is no longer in the data. Reopening it shows the question, and re-asking it gets a fresh answer from the agent.
- **History is full**: the user reaches the saved-scenario limit. The oldest scenario not opened recently is removed to make room, and the user is told which one.
- **Map data still loading or failed**: the history list can still be browsed, but reopening a scenario waits for the data, or shows the usual failed state with Retry.
- **Same track drawn twice**: it creates two entries, because they are separate explorations.
- **A click without a drag**: a single-point track is saved and reopened like any other.

## Requirements *(mandatory)*

### Functional Requirements

**Saving**

- **FR-001**: The system MUST save a scenario to the history as soon as its track is drawn. From then on, every change MUST be saved immediately: a redrawn track, category, reach cutoff, a new question, or a rename. Reloading the page or closing the tab MUST NOT lose the scenario in progress.
- **FR-001a**: The scenario in progress MUST appear in the history list, highlighted as the current one.
- **FR-001b**: A **New simulation** control MUST replace the existing Reset control. It clears the map, scenario lists and chat for a new scenario and leaves the current one saved in the history. A new history entry is created only when a track is then drawn.
- **FR-001c**: Redrawing the track within a scenario MUST replace that scenario's track and MUST NOT create a new history entry. Changing the category or reach cutoff likewise stays in the same scenario.
- **FR-002**: A saved scenario MUST contain only the user's inputs: the drawn track, the category, the reach cutoff, the questions asked with when they were asked, a name, and created / last-opened times.
- **FR-003**: The system MUST NOT save any computed results with a scenario: affected counties or shelters, the receiving list, summaries, registry figures, simulated distances, or agent answers.
- **FR-004**: The system MUST NOT save any Google Maps content (titles, links, text) with a scenario (feature 001 FR-022, Constitution II).
- **FR-005**: The system MUST NOT create a history entry for a simulation in which no track was drawn.

**Reopening**

- **FR-006**: The history list MUST be a collapsible **History** section at the top of the chat column, above the conversation. Its header always shows the number of saved scenarios (e.g. "History (5)"). It starts collapsed, opens or closes with one click, and the user MUST be able to select a scenario from it with a single click. The section says the history is saved in this browser only (FR-015).
- **FR-007**: Selecting a saved scenario MUST restore its track, category and reach cutoff on the map, and recompute every result from current data using the same rules as a newly drawn scenario.
- **FR-008**: A reopened scenario MUST be labelled as re-simulated, with the time it was re-simulated, and MUST NOT present any result as having been saved.
- **FR-009**: A reopened scenario MUST list its earlier questions and let the user re-ask any of them with one action. The answer is new, with fresh Google Maps sources where grounded.
- **FR-010**: New questions asked in a reopened scenario MUST be added to that scenario's saved questions.

**Managing**

- **FR-011**: The history list MUST be ordered by last opened, newest first. Each entry shows its name, category, crossed counties (abbreviated) and last-opened time.
- **FR-012**: A new scenario MUST get a default name built from its category and the first and last county its track crosses.
- **FR-013**: The user MUST be able to rename and delete saved scenarios. Deleting requires confirmation.
- **FR-014**: The history MUST hold at least 50 scenarios. When full, it removes the least recently opened one and tells the user which one was removed.

**Scope of the history**

- **FR-015**: Saved scenarios MUST be stored **in this browser on this device only**. They are not sent to the agent service or shared with other users or devices. Clearing the browser's site data removes the history. The history list MUST say this, e.g. "Saved in this browser only".
- **FR-016**: For each saved question, the history MUST keep **only the question text** and when it was asked. Agent answers are never saved. A reopened scenario lists its questions, and re-asking one gets a fresh answer from current data.

### Key Entities

- **Saved Scenario**: one past simulation session. It holds the drawn track, category (1–5), reach cutoff, name, created time, last-opened time, and the saved questions. It never holds computed results or Google Maps content.
- **Saved Question**: a question the user asked in that scenario, with when it was asked. It never includes the answer. It belongs to exactly one Saved Scenario.
- **History**: the list of Saved Scenarios kept in this browser (FR-015), ordered by last opened, capped per FR-014.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can return to any of their last 10 scenarios in under 10 seconds from the main screen, in two clicks or fewer (open History in the chat column, pick the entry).
- **SC-002**: In 100% of tested reopenings, the restored track, category and reach cutoff match what was drawn.
- **SC-003**: Reopening an unchanged scenario against unchanged data gives results identical to the original in 100% of tested cases. After a data change, the results reflect the change in 100% of tested cases.
- **SC-004**: A reopened scenario's results are on screen within 2 seconds once map data has loaded, the same target as a freshly drawn scenario.
- **SC-005**: Inspecting the stored history in tests finds no computed results and no Google Maps titles, links or text (0 occurrences).
- **SC-006**: Starting a new simulation never loses the previous one: across 20 scripted draw → ask → new cycles, all 20 scenarios appear in the history.
- **SC-007**: A reload at any point after a track is drawn loses nothing: the track, settings and every question asked before the reload are present after it (100% of tested reloads).

## Assumptions

- **Users**: the same county or state emergency planners as feature 001, using it to plan, not for live operations.
- **What triggers a save**: a scenario is saved continuously from the moment its track is drawn (see Clarifications). There is no Save button. This matches how chat history behaves.
- **Re-simulation**: "re-simulated" means the band, affected set and receiving list are recomputed with the illustrative rules from feature 001 against the shelter data loaded in the current session.
- **Chat in a reopened scenario**: reopening starts a fresh conversation with the agent, using that scenario's context. Earlier answers are not fed back to the agent.
- **Default name**: a scenario's default name follows its track (e.g. it updates when the track is redrawn) until the user renames it. After a rename, the user's name is kept.
- **Limit**: 50 saved scenarios is enough for one planning season. Older ones are removed oldest first, and the user is told.
- **Private browsing and cleared data**: in a private window, or after the browser's site data is cleared, the history may be empty. The app still works and simply starts a new history.
- **Out of scope**: syncing history across devices or users, comparing two scenarios side by side, exporting or sharing a scenario as a file or link, and showing how a scenario's results changed over time.
