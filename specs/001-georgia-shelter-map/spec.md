# Feature Specification: Georgia Shelter Readiness Map

**Feature Branch**: `001-georgia-shelter-map`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Frontend application that displays the state of Georgia with hoverable,
highlighted counties and a map of shelters for hurricane planning; a chat window where the user asks
the backend agent questions (e.g. for Cobb County, how many shelters are available and what is their
capacity?); the ability to click and drag a simulated hurricane and assign its intensity (Category
1–5). Track: Shelter Readiness — which shelters can take the people who will actually arrive, and
which are themselves in the surge zone? Planning in August for a storm that has not formed yet."

## Readiness Scenario & Data Honesty *(mandatory)*

**Scenario**: Our agent helps a **county emergency manager** in **Georgia** decide **which shelters
to verify, re-designate or replace** before **the peak of hurricane season (September)**.
**Track / State**: Shelter Readiness / Georgia (GA)
**Brief segments served**: Where they would go and whether that holds up (primary); What to fix
before the season; What we could not tell you. *Who cannot leave* is shown only as county context in
this feature (no-vehicle households, 65+ share, disability share (ACS survey estimate) in the county summary).
**Unrecorded handling**: The flags shown are wheelchair access, generator on site, medical-needs
designation and surge-zone location. Each is shown as **Yes / No / Not recorded**, with all three
counts given for every county and every answer. In Georgia, 75% of shelters have no recorded
wheelchair-access value.
**World vs paperwork**: Shelter counts, capacities and flags are the **federal registry record**
(paperwork). Whether a shelter still exists, its current name and whether it is open come from a
**live map check** (world). The simulated hurricane is an **illustrative planning scenario**, not a
forecast. The screen labels each figure with which of these it is.
**What we could not tell you**: Accessibility for roughly three in four shelters. Whether any shelter
will be open during a real storm. Drive times (unless a live routing check was run). Any figure
finer than the county for power-dependent residents. The real reach of a hurricane's surge or wind,
because the simulation is illustrative.

## Clarifications

### Session 2026-10-27

- Q: Where does the map get its shelter and county data? → A: Everything goes through the backend
  agent. The map requests its data from the agent, and the chat goes to the agent too.
- Q: How are receiving shelters ranked? → A: Keep only shelters within the "within reach" cutoff,
  then sort by largest recorded capacity.
- Q: What is the default "within reach" cutoff, and can it be changed? → A: 80 km (~50 mi) to
  start, adjustable on screen from 25 to 200 km.
- Q: Should the county summary include context about who cannot leave? → A: Yes. Add households
  with no vehicle, share aged 65+, and share with a disability (modeled; corrected in plan R10 to ACS survey estimate), each with its source. No
  map shading.
- Q: Who can open the deployed app? → A: It is deployed, but open only to signed-in Google
  accounts on an allow-list (team plus invited judges).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explore Georgia's shelters by county (Priority: P1)

An emergency planner opens the application and sees a map of Georgia with all 159 counties and the
registered shelters plotted. Moving the pointer over a county highlights it. A summary appears
showing the county name, number of shelters, total recorded evacuation capacity, and how many
shelters are recorded Yes / No / Not recorded for wheelchair access, and how many sit in a recorded
surge zone. Selecting a shelter shows its own record.

**Why this priority**: It is the foundation everything else is shown on. On its own it already
answers "what is on file for my county, and how much of it is blank?"

**Independent Test**: Open the app with no chat and no simulation. Hover over Cobb County and Chatham
County, and check that the highlight and summary figures match the shelter registry for those
counties.

**Acceptance Scenarios**:

1. **Given** the map is loaded, **When** the user hovers over any county, **Then** that county alone
   is visibly highlighted and its summary appears within a moment; moving off clears the highlight.
2. **Given** a county whose shelters mostly have no wheelchair record, **When** its summary shows,
   **Then** the "Not recorded" count is displayed alongside Yes and No and is never added to No.
3. **Given** a county containing a shelter with an implausible capacity (e.g. Commerce, Jackson
   County), **When** its summary shows, **Then** the total excludes that shelter and names it with a count beside the total
   (e.g. "Excludes 2 shelters with suspect capacity: …"), and the total including it is also shown.
4. **Given** the user selects a shelter on the map, **When** its details open, **Then** they show
   name, address, capacity, use (before landfall / after impact), each flag as Yes / No / Not
   recorded, and a label stating this is the registry record and when it was registered, if known.

---

### User Story 2 - Ask the agent about a county or shelter (Priority: P1)

The planner types a question in the chat panel, such as *"For Cobb County, how many shelters are
available and what is their capacity?"* The agent answers in plain language. The answer gives the
counts, says which figures come from the registry and which were checked live, says how many
shelters had no record for the relevant flag, and puts map sources directly under any live-checked
statement. The shelters and county the answer refers to are highlighted on the map.

**Why this priority**: This is how the readiness questions get answered. The map shows the record;
the agent interprets it, checks it against the live world, and says what to do.

**Independent Test**: Ask the Cobb County example question and two others ("Which shelters in
Chatham County are in the surge zone?", "Which of those can take a wheelchair?"). Check the numbers
against the registry, confirm unrecorded counts are stated, and confirm the referenced items are
highlighted on the map.

**Acceptance Scenarios**:

1. **Given** the chat is open, **When** the user asks how many shelters a county has and their
   capacity, **Then** the answer states the count and total capacity, flags any suspect capacity,
   and labels them as registry figures.
2. **Given** the user asks which shelters can take a wheelchair, **When** most have no record,
   **Then** the answer separates "recorded yes", "recorded no" and "nobody has assessed", and never
   says "none are accessible" unless all are recorded No.
3. **Given** the agent checked a shelter against the live map, **When** the answer is shown,
   **Then** live-checked claims are marked as current, map source links appear immediately after
   them, and any disagreement with the registry (renamed, closed, different use) is stated.
4. **Given** an answer refers to specific shelters or counties, **When** it is shown, **Then**
   those items are highlighted on the map, and the user can select one from the answer to focus
   the map on it.
5. **Given** the agent cannot be reached or takes too long, **When** the user sends a question,
   **Then** the chat shows a clear status (working / failed, try again) and the map keeps working.

---

### User Story 3 - Place a simulated hurricane and see which shelters it puts at risk (Priority: P2)

The planner clicks and drags across the map to draw a hurricane track, for example from offshore
across the Glynn County coast and inland, and sets its intensity from Category 1 to 5. The map
shows a simulated impact band along the track and highlights the counties and shelters inside it.
Shelters that are both inside the band and recorded as in a surge zone stand out. A side summary
counts affected shelters and their recorded capacity, with Yes / No / Not recorded for wheelchair
access and generator. A second list shows **where people would go**: shelters outside the band,
within reach and sorted by capacity, with their accessibility status. The planner can ask the agent
about the current scenario (e.g. *"Which of these receiving shelters can actually take a
wheelchair?"*).

**Why this priority**: This makes the readiness question concrete ("if a Category 3 makes landfall
near Brunswick, which of my shelters are out?"). It needs Stories 1 and 2 first and is the main
thing on screen in the demo.

**Independent Test**: Draw a Category 3 track across the Glynn County coast and inland. Check that
the affected summary and receiving list change when the category or track changes, that surge-zone
shelters inside the band are distinguished, and that no receiving shelter lies inside the band.

**Acceptance Scenarios**:

1. **Given** the map, **When** the user clicks and drags to draw a track, **Then** the track and its
   impact band are drawn, and affected counties and shelters update when the drag ends.
2. **Given** a drawn track, **When** the user changes the category from 1 to 5, **Then** the band
   widens or narrows and the affected counts and receiving list update to match.
3. **Given** a drawn track, **When** the affected summary is shown, **Then** it is labeled as
   an illustrative scenario, not a forecast, and lists shelters inside the area that the registry
   records as in a surge zone.
4. **Given** a drawn track, **When** the user asks the agent about it, **Then** the agent
   receives the scenario (track, category, affected counties) and its answer refers to it.
5. **Given** a drawn track, **When** the user removes or resets it, **Then** the map returns
   to the plain county view.
6. **Given** a drawn track, **When** the receiving list is shown, **Then** it ranks shelters
   outside the band and within reach by capacity (largest first), labels distances as straight-line, shows wheelchair
   access as Yes / No / Not recorded, and states the yes · no · not recorded wheelchair counts in its header.

---

### User Story 4 - Readiness gaps and "what we could not tell you" (Priority: P3)

From a county or scenario, the planner asks for a short list of shelters to verify or fix before the
season. The agent returns a ranked list with a reason per row (e.g. "in surge zone", "accessibility
never recorded", "renamed per live check", "capacity looks wrong"). The list ends with a counted
statement of what could not be determined.

**Why this priority**: This is the deliverable the track asks for. It depends on the agent's
judgment more than on the screen, so the frontend's part is presenting it clearly.

**Independent Test**: Ask "What should I verify before September in Chatham County?" Check that you
get a ranked list with reasons and a separate counted "could not tell you" section.

**Acceptance Scenarios**:

1. **Given** a county, **When** the user asks what to fix before the season, **Then** the answer is
   a ranked list with one reason per shelter and the shelters are highlighted on the map.
2. **Given** any readiness list, **When** it is shown, **Then** it ends with a "What we could not
   tell you" section giving counts (e.g. "41 shelters never assessed for wheelchair access").

---

### Edge Cases

- The agent is slow or unreachable when the session starts: county outlines still render, shelter
  markers and summaries show a loading or failed state, and the user can retry. No partial counts
  are presented as complete.
- A county with zero registered shelters: the summary says "No shelters on file", not "0 capacity
  available" with no explanation.
- The pointer moves quickly across many counties: only the county under the pointer is highlighted,
  and no stale summary is left showing.
- A shelter whose coordinates fall outside Georgia, or outside the county it is filed under: it is
  shown under its recorded county, marked "location disagrees with record", and not silently placed
  in another county.
- Suspect capacities (Commerce High School 270,135 and Commerce Primary School 225,112 spaces): they
  are flagged in every total they touch, and both totals (with and without) are available.
- The track starts at sea or leaves the state: the band may extend beyond Georgia, but only Georgia
  counties and shelters are counted.
- A very short track (a click without a drag): it is treated as a single point, with a circular
  band of the category's width.
- A Category 5 band so wide that few or no shelters remain outside it: the receiving list says so
  plainly and does not rank shelters inside the band.
- No shelters lie outside the band within the current reach cutoff: the receiving list says "No
  shelters within N km outside the affected area" and suggests raising the cutoff. It never shows
  an empty list with no explanation.
- A receiving shelter recorded as in a surge zone: it stays in the list with that flag shown.
- The agent answers a question unrelated to Georgia shelter readiness: it is shown, but no map
  highlighting is attempted.
- A live check says a shelter has closed or been renamed: the shelter stays on the map with a
  visible discrepancy marker. It is not removed, because the registry record is not edited.
- Someone opens the URL without being signed in, or with an account not on the allow-list: they are
  refused access and no shelter data or agent call is made.
- The user asks for information about individual people: the agent declines, and the screen never
  shows individual-level data.

## Requirements *(mandatory)*

### Functional Requirements

**Map**

- **FR-001**: The system MUST display a map of Georgia showing the boundary of all 159 counties.
- **FR-002**: The system MUST highlight the county under the pointer and remove the highlight when
  the pointer leaves it.
- **FR-003**: On hover or selection, the system MUST show a county summary: name, shelter count,
  total recorded evacuation capacity, and Yes / No / Not recorded counts for wheelchair access,
  generator on site, medical-needs designation and surge-zone location. All three counts are always
  shown for every flag, never only the Yes count.
- **FR-003a**: The county summary MUST also show three people figures, each labeled with its source:
  **households with no vehicle** (count), **share of residents aged 65+**, and **share of residents
  with a disability**. Disability MUST be labeled with its source and estimate type (ACS survey estimate via CDC SVI). Figures MUST be aggregated
  from census tracts to the county. Map shading MUST NOT encode these figures, and the summary MUST
  NOT combine them into a single risk score.
- **FR-004**: The system MUST plot every registered Georgia shelter at its recorded location and let
  the user open a shelter's details.
- **FR-005**: Shelter details MUST show each flag as Yes, No or Not recorded, and MUST show "Not
  recorded" for blank values, including values that are only whitespace.
- **FR-006**: The system MUST visually distinguish shelters recorded as in a surge zone, and
  shelters designated for use before landfall versus after impact.
- **FR-007**: The system MUST flag shelters with implausible capacities (below 0 or above 100,000).
  Every capacity total that leaves any shelter out MUST state, right next to the total, **how many**
  shelters were left out and **which ones** by name (e.g. "Excludes 2 shelters with suspect
  capacity: Commerce High School, Commerce Primary School"). Wherever such a total appears, the
  total including them MUST also be available.
- **FR-008**: The system MUST NOT edit, drop or hide registry records. Data problems are shown as
  flags.
- **FR-008a**: The map's shelter and county data MUST be obtained from the backend agent, the same
  single entry point the chat uses. It MUST be requested once when the session starts, as a
  structured (not prose) response, and reused for every hover and summary in that session. Hovering
  MUST NOT trigger a request to the agent.
- **FR-008b**: While the initial data load is in progress, the map MUST show county outlines with a
  visible loading state. If the load fails, it MUST show an error with a retry option.
- **FR-009**: The system MUST provide a legend explaining every color, marker and flag, including
  "Not recorded".

**Chat**

- **FR-010**: The system MUST provide a chat panel where the user types a question and receives the
  agent's answer, with the conversation visible for the session.
- **FR-011**: The system MUST send the agent the current context with each question: the selected
  or hovered county, any selected shelter, and the active hurricane scenario.
- **FR-012**: The system MUST display map sources immediately after each live-checked statement in
  an answer, reachable without more than one interaction, with the source name shown exactly as
  provided and never translated.
- **FR-013**: The system MUST visually distinguish live-checked (current) statements from registry
  (historical) statements in answers.
- **FR-014**: When an answer refers to specific counties or shelters, the system MUST highlight
  them on the map and let the user select them from the answer.
- **FR-015**: The system MUST show a visible working state while the agent is answering, and a clear
  failure message with a retry option if it fails. The map MUST stay usable throughout.

**Hurricane simulation**

- **FR-016**: The user MUST be able to place a simulated hurricane on the map by dragging it, and
  reshape it afterwards. The simulated hurricane is a **track the user draws** by clicking and
  dragging across the map. Its impact area is a band along that track, and the band's width grows
  with category.
- **FR-017**: The user MUST be able to set the simulated hurricane's intensity to Category 1, 2, 3,
  4 or 5. The impact area MUST grow with category, using fixed, documented values per category.
- **FR-018**: The system MUST highlight the counties and shelters inside the simulated impact area
  and summarize them: count, recorded capacity (per FR-007), and Yes / No / Not recorded counts for
  wheelchair access, generator and surge-zone location.
- **FR-018a**: For an active scenario, the system MUST also list **receiving shelters**: Georgia
  shelters outside the impact band whose straight-line distance from the center of the nearest
  affected county is within the "within reach" cutoff, sorted by recorded evacuation capacity,
  largest first. Ties are broken by shorter distance. Accessibility and generator status MUST NOT
  affect the order. Each row MUST show capacity, distance, wheelchair access and generator as Yes / No /
  Not recorded, and one reason for its rank. Receiving shelters MUST be highlighted on the map
  differently from affected ones.
- **FR-018b**: Distances in the receiving list MUST be labeled straight-line unless a live drive
  time was obtained. The "within reach" cutoff MUST be one documented, visible setting, not a
  hidden constant. It starts at **80 km (~50 mi)**, and the user can change it on screen anywhere
  from **25 km to 200 km**. Changing it MUST update the receiving list, and the list MUST show the
  cutoff in effect.
- **FR-018c**: Ranking MUST NOT treat Not recorded wheelchair access as No. Shelters recorded Yes,
  recorded No and Not recorded MUST stay distinguishable in the list. The list header MUST state
  the wheelchair-access counts for the receiving shelters as Yes / No / Not recorded (e.g. "4 yes
  · 1 no · 17 not recorded").
- **FR-018d**: Suspect-capacity shelters in the receiving list MUST stay visible and flagged, MUST
  NOT outrank other shelters on their recorded capacity, and MUST be left out of any capacity total,
  with the exclusion stated per FR-007.
- **FR-019**: The system MUST label all simulation output as an illustrative planning scenario and
  not a forecast.
- **FR-020**: The user MUST be able to remove or reset the simulated hurricane.

**Data boundaries**

- **FR-021**: The system MUST NOT display or request individual-level personal data, including
  shelter contact names.
- **FR-022**: The system MUST NOT store map-service results other than place identifiers.

**Access**

- **FR-023**: The deployed application, and the agent it calls, MUST be reachable only by
  signed-in Google accounts on an allow-list (the team plus invited judges). A user who is not
  signed in or not on the list MUST be refused before any data loads or any agent call is made.
- **FR-024**: Adding or removing an allowed account MUST NOT require a code change or a
  redeployment.

### Key Entities

- **County**: One of Georgia's 159 counties. Has a name, boundary, a summary of its shelters and
  their recorded flags, and people context (households with no vehicle, share aged 65+, survey-estimated
  share with a disability) aggregated from its census tracts.
- **Shelter**: A registry record. Has name, address, recorded location, county, evacuation
  capacity, use (before landfall / after impact), and flags for wheelchair access, generator on
  site, medical-needs designation and surge-zone location, each Yes / No / Not recorded. It may
  also carry data-quality flags (suspect capacity, location disagrees with record) and a live-check
  result (exists / renamed / closed / unknown, with when it was checked and the map sources).
- **Hurricane Scenario**: A simulated storm with a user-drawn track, category 1–5, a derived impact
  band (width per category), the affected counties and shelters, and a ranked list of receiving
  shelters. It is illustrative only and lasts for the session.
- **Receiving Shelter Entry**: A shelter outside the impact band, with recorded capacity,
  straight-line distance from the affected area, accessibility and generator status (Yes / No /
  Not recorded), rank, and a one-line reason.
- **Chat Exchange**: A user question, its context (county, shelter, scenario), and the agent's
  answer, including referenced counties and shelters, live-checked statements and their sources,
  and the "could not tell you" counts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can find the shelter count and total capacity for any named Georgia
  county in under 15 seconds, by hover or by asking the chat.
- **SC-002**: County summary figures match the registry for 100% of counties checked, including the
  Not recorded counts.
- **SC-003**: In a scripted test of 10 accessibility questions, the system never presents an
  unrecorded value as "no" (0 of 10).
- **SC-004**: Hover highlighting follows the pointer with no visible lag, and the summary appears
  within half a second of entering a county.
- **SC-004a**: Shelter markers and county summaries are available within 20 seconds of opening the
  application (initial load from the agent).
- **SC-005**: After drawing or changing the simulated hurricane, the affected summary and receiving
  list update within 2 seconds.
- **SC-005a**: Changing the reach cutoff updates the receiving list within 1 second, and the cutoff
  in effect is always visible next to the list.
- **SC-005b**: In every tested scenario, no shelter inside the impact band appears in the receiving
  list, and the receiving list's Not recorded accessibility count matches the registry.
- **SC-006**: Every agent answer that contains a live-checked claim shows its map sources directly
  beneath that claim (100% of checked answers).
- **SC-007**: In a 3-minute demo, a presenter can go from an empty map to a drawn Category 3 track,
  a list of affected surge-zone shelters, a ranked receiving list, and an agent answer about which
  receiving shelters can take a wheelchair, with no error.
- **SC-008**: A county emergency manager reviewing the screen can tell, without explanation, which
  figures are registry records, which are live checks, and which are simulation (validated with at
  least one reviewer).

## Assumptions

- **Primary user** is a county or state emergency planner preparing in August, not a member of the
  public seeking directions during a storm. The tool is not for real-time operations, and no
  shelter is presented as "open" for an actual event.
- **State** is Georgia only. Data comes from the challenge's prepared shelter, tract, hazard, care
  facility and power-dependence tables for GA.
- **The backend agent** (built separately) answers questions, performs live map checks and ranks
  shelters. It is also the only source of the map's data (see Clarifications), so it must be able
  to return Georgia shelters and county summaries in a structured form. This feature is the screen
  and the chat client. It does not re-implement the agent's
  judgment.
- **Surge zone** means the registry's recorded surge-area flag, and is not derived from the
  simulation.
- **Band width per category** is a fixed, illustrative table documented in the plan (loosely based
  on typical hurricane-force wind radii). It is not a surge or wind model.
- **Distance** in the receiving list is straight-line. Drive times appear only where the agent has
  obtained them from a live routing check, and they are labeled as such.
- **Receiving-list ranking** keeps shelters within the reach cutoff and sorts them by capacity
  (see Clarifications). Accessibility is shown but never used to sort. The agent may explain the
  ranking or add to it in chat, but the list's order follows this rule.
- **County boundaries** come from a public-domain US Government source.
- **The team has asked for React.** Technology choices are recorded in the implementation plan, not
  here.
- **No in-app accounts or roles.** Access is controlled at the door by a Google sign-in allow-list
  (see Clarifications). Every allowed user sees the same thing. Chat history and scenarios last for
  the session only and are not shared between users.
- **Desktop browser** is the primary target. Phone layout is out of scope for this feature.
