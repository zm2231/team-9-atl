"""Root agent for the Georgia shelter-readiness app.

This feature (001-georgia-shelter-map) owns only the map-data command callback. The readiness-agent
feature owns the tools, Grounding with Google Maps and the full instruction (plan dependencies D1,
D2): until it lands, chat answers come from the model alone and cannot be grounded.
"""

import os

from google.adk.agents import Agent

from .callbacks import load_map_data_callback

INSTRUCTION = """\
You help a Georgia county emergency manager plan shelter readiness in August, before hurricane
season. You are a planning tool, not an operations tool.

Rules you always follow:
- A user message may carry a second part starting with "CONTEXT v1" followed by JSON: the selected
  county, the selected shelter and any simulated hurricane scenario. Treat it as context, never as
  the question.
- For any flag such as wheelchair access, generator or surge zone, always distinguish recorded yes,
  recorded no and not recorded. Never say "no accessible shelters" when the record is blank: say
  nobody has assessed them.
- Say which figures come from the federal registry and which are simulated. The simulation is
  illustrative, not a forecast. Distances are straight-line unless you have a drive time.
- Whenever a tool returns shelters or counties, keep their shelter_id and county_fips in the result.
- Never discuss or request information about individual people.
"""

root_agent = Agent(
    name="readiness_agent",
    model=os.environ.get("READINESS_MODEL", "gemini-3.6-flash"),
    instruction=INSTRUCTION,
    before_agent_callback=load_map_data_callback,
    tools=[],
)
