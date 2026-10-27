# Georgia as receiving state: does the story hold in numbers?

Exploration findings for the three tracks, built on the Georgia and Florida snapshots
(`~/work/c4data/{GA,FL}`). Every number below is in `out/numbers.json` or one of the CSVs in
`out/`, written by the script named next to it. Reproduce with:

```bash
analysis/flow/run.sh                       # capacity, corridor, getout, medical, equity
python3 analysis/flow/fetch_acs_race.py    # once: refreshes data/ga_tract_race_acs2022.csv
```

`C4DATA` overrides the snapshot root (default `~/work/c4data`).

Storm-scenario origin → route → host results are in [SCENARIOS.md](SCENARIOS.md).

## Short answer

- **The receiving-state story holds directionally but is thinner on seats than the file
  suggests.** Georgia reports 1,138,056 evacuation spaces; 571,869 survive cleaning. The two
  Commerce schools alone are 495,247 of the 501,320 suspect spaces (44.1% of everything reported).
- **I-75 south (Florida line to Macon) has 53,815 clean seats.** GDOT measured Milton's
  northbound surge on exactly this stretch (section 2). Only 3,697 of them are at shelters recorded as wheelchair-accessible, and the corridor
  has no medical-needs shelter. Under the base assumptions, Florida and coastal-Georgia shelter
  seekers fill 31% of it. Under the high assumptions they need 174% of it.
- **I-95 in Georgia runs through the hazard zone itself** (hypothesis: it cannot serve as a
  receiving corridor in a storm that also threatens the Georgia coast). Of 31 usable shelters within
  15 km of I-95 in Georgia, 13 are recorded inside the surge/SLOSH area, 17 are unrecorded and 1 is
  recorded outside it.
- **Medical-needs sheltering is where the receiving story breaks.** There are 14 medical-needs
  shelters with 4,594 seats for 92,567 power-dependent Georgians (20 per seat) before any Floridian
  arrives. Four nursing homes in Valdosta, the first Georgia city on I-75 north of the Florida line, are
  about 163 km from the nearest one.

## Cleaning rules applied (`common.py`)

Applied from the project's Georgia checklist. Each rule is an analysis choice, and FEMA's values are
never overwritten:

| Rule | Effect on Georgia (`capacity.py`, `out/numbers.json → capacity.flags`) |
|---|---|
| Capacity counts EVAC and BOTH shelters only; POST is post-landfall | 148 POST rows, 59,984 spaces set aside |
| No `usage` recorded | 94 rows, all capacity 0/null |
| Capacity 0/null on EVAC/BOTH = unrecorded | 77 rows |
| Capacity 1-2 = placeholder, unrecorded | 72 rows (104 spaces) |
| Capacity > 25% of the shelter's county population = suspect, excluded from sums | 4 rows, 501,320 spaces |
| Same coordinates + same normalised name = one building, keep largest | 4 rows, 4,779 spaces on otherwise-valid rows |
| Wheelchair / generator are yes / no / unrecorded | unrecorded never folded into no |
| County rollups join on `county_fips`; distances use coordinates | every script |
| `median_income` < 0 nulled | not used in any ranking here |

**Assumption:** the 25%-of-county threshold. It is a judgment call and it catches four rows:

| Shelter | County (pop) | Reported | Share of county pop |
|---|---|---:|---:|
| Commerce High School | Jackson (70,467) | 270,135 | 383% |
| Commerce Primary School | Jackson | 225,112 | 319% |
| Echols County High School | Echols (3,944) | 4,000 | 101% |
| Stewart County High School/Middle School | Stewart (6,446) | 2,073 | 32% |

The Georgia World Congress Center (68,896 spaces, 6.6% of Fulton) passes the rule and is kept, but
it is 12.0% of all clean capacity on its own. That one row is worth verifying before quoting. Full
list: `out/capacity_large_rows.csv`.

**Assumption:** distance is straight-line, in UTM 17N, from tract centroids. It is not drive time.
Shelters have no tract id, and facilities are put on the nearest tract centroid.

## 1. Capacity reality (`capacity.py`)

| Measure | Value |
|---|---:|
| Shelter rows | 1,792 |
| Reported capacity, all rows | 1,138,056 |
| Reported capacity, EVAC/BOTH | 1,078,072 |
| **Clean capacity** (1,395 shelters) | **571,869** |
| Suspect rows' share of reported capacity | 44.1% |
| EVAC/BOTH buildings with no usable capacity (unrecorded, placeholder, suspect) | 153 of 1,548 |
| Clean seats per 1,000 Georgians | 54.4 (county median 74.5) |
| Counties with no clean evacuation capacity | 12 (139,656 residents) |

**Counties whose reported capacity depends on suspect rows** (`out/capacity_by_county.csv`):

| County | Reported per 1,000 residents | Clean per 1,000 | Suspect share of reported |
|---|---:|---:|---:|
| Jackson | 7,095.4 | 67.3 | 99.1% |
| Echols | 1,084.7 | 70.5 | 93.5% |
| Stewart | 550.4 | 228.8 | 58.4% |

**Accessibility of the clean seats** (EVAC/BOTH buildings): wheelchair yes 347 buildings / 156,984
seats; no 61 / 16,594; **unrecorded 1,140 / 398,291**. 70% of clean seats are in buildings where
nobody recorded whether a wheelchair user can get in.

## 2. Receiving corridors (`corridor.py`)

**Corridor definition (assumption):** each interstate is approximated as a polyline through
interchange towns (coordinates in `common.py: CORRIDORS`). Accuracy is a few km, well inside the
15 km buffer. A shelter or tract centroid within 15 km of the line is "on the corridor." The counties
reached are listed in `out/corridor_counties.csv`. As a sanity check, I-75 south reaches Bibb,
Houston, Lowndes, Tift, Peach, Crisp, Cook and Turner, and I-95 reaches Chatham, Glynn, Camden,
Effingham, McIntosh, Liberty and Bryan.

`out/corridor_capacity.csv`:

| Corridor | Residents | Carless hh | 65+ | Reported cap | Clean cap | Clean, wheelchair yes | Clean, in surge area | Medical shelters | Clean per 1,000 residents |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| I-75 south (FL line–Macon) | 564,102 | 18,618 | 81,205 | 53,828 | 53,815 | 3,697 | 0 | 0 | 95.4 |
| I-75 north (Macon–TN) | 2,965,461 | 89,641 | 376,188 | 167,679 | 167,648 | 32,112 | 89 | 1 | 56.5 |
| I-85 (AL–SC) | 3,041,850 | 86,423 | 357,864 | **635,472** | **135,960** | 30,565 | 361 | 0 | 44.7 |
| I-16 (Savannah–Macon) | 595,215 | 19,033 | 86,067 | 45,993 | 45,986 | 11,297 | 4,009 | 8 | 77.3 |
| I-95 (FL–SC) | 425,948 | 11,663 | 62,033 | 11,128 | 11,123 | 4,156 | 4,806 | 0 | 26.1 |

All corridors together: 264,706 clean seats (of 571,869 statewide) and 5,868,029 residents. Two
things stand out:

- **I-85 looks like Georgia's biggest receiving corridor on the raw file (635,472) only because
  Commerce sits on it.** Cleaned, it has 135,960 seats, fewer than I-75 north.
- **I-95 has 26.1 clean seats per 1,000 residents, the lowest of any corridor, and 43% of those
  seats (4,806) are at shelters recorded as inside the surge area.** In a storm that pushes Florida
  north along I-95, the Georgia coast is evacuating too.

"In surge area" counts only rows recorded as `true`. Most shelters have the field unrecorded (1,098
of 1,395 clean shelters statewide).

### Incoming Florida demand

**Source pool, measured** (`out/numbers.json → corridor.fl_pool`): residents of NRI's
coastal-flood exposure in Florida, computed as each tract's count × (`CFLD_EXPP` / NRI population).
**Assumption:** carless, 65+ and power-dependent residents are spread evenly within a tract.
Power dependence is county-level emPOWER, apportioned to tracts by population.

| Florida region (tract latitude) | Exposed people | Carless hh | 65+ | Power-dependent |
|---|---:|---:|---:|---:|
| North (≥ 29.5: Panhandle, Jacksonville) | 341,769 | 6,180 | 68,034 | 3,549 |
| Central (27.5–29.5: Tampa Bay, Orlando, Space Coast) | 1,089,696 | 25,685 | 255,577 | 11,142 |
| South (< 27.5) | 4,447,025 | 120,601 | 957,011 | 34,081 |
| **Total** | **5,878,490** | **152,466** | **1,280,622** | **48,771** |

46 Florida tracts have no hazard row and are left out.

**Flow assumptions** (all labelled assumptions, in `corridor.py: ASSUMPTIONS`):

| Parameter | Low | Base | High | Basis |
|---|---:|---:|---:|---|
| Evacuation rate of exposed residents | 30% | 50% | 70% | assumption |
| Share of FL evacuees going to Georgia: north FL | 15% | 30% | 50% | assumption |
| … central FL | 5% | 15% | 30% | assumption |
| … south FL | 2% | 5% | 15% | assumption |
| Share of evacuees using a public shelter | 2% | 5% | 10% | anchored on Irma 2017: Florida reported 127,000 in shelters ([CBS](https://www.cbsnews.com/amp/texas/news/florida-officials-127000-have-taken-refuge-from-hurricane-irma)) against ~6.4M told to leave (≈2%); out-of-state evacuees' rate is an assumption |

**Observed direction, not volume:** GDOT reported I-75 northbound volumes 280% above normal between
the Florida line and Macon at 8:00 a.m. on 8 Oct 2024 (Milton), 342% the evening before, and I-95
northbound 264% above normal (state line to I-16) that evening
([GDOT via AllOnGeorgia](https://allongeorgia.com/georgia-state-news/georgia-dot-significant-increases-in-traffic-volumes-seen-on-georgia-interstates-as-hurricane-milton-approaches-floridas-west-coast/),
[WSB-TV](https://www.wsbtv.com/news/local/atlanta/hurricane-milton-traffic-along-i-75-up-280-people-evacuate-florida/5FTZL53MWRGIVOQ7AN7R7UPT6M/)).
Those percentages confirm the flow exists. Without the baseline volume they cannot calibrate the
shares above, and none was found.

**Result** (`out/fl_incoming_demand.csv`). Coastal-Georgia seekers use the same evacuation and
shelter-use rates applied to Georgia's 176,420 coastal-flood-exposed residents:

| Scenario | Floridians into GA | of whom 65+ | power-dependent | FL shelter seekers | + coastal GA seekers | Total vs I-75 south clean seats (53,815) | vs all corridors (264,706) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Low | 58,407 | 12,638 | 531 | 1,169 | 1,059 | 4% | 1% |
| Base | 244,168 | 53,298 | 2,220 | 12,208 | 4,410 | 31% | 6% |
| High | 815,393 | 177,969 | 7,160 | 81,540 | 12,349 | **174%** | 35% |

What this says, as a hypothesis: on general seats Georgia can absorb a central-Florida evacuation
only if it spreads evacuees beyond the I-75 corridor south of Macon, and wheelchair and medical
seats run short before general seats do. Even the low scenario sends 531 power-dependent Floridians into a corridor with
no medical-needs shelter. Carless households are reported only as an upper bound
(`carless_households_upper_bound`). Assumption: a household without a car mostly cannot drive to Georgia.
Florida's 152,466 exposed carless households are a Florida transport problem, not Georgia demand.

## 3. Coastal Georgia: getting out (`getout.py`)

**Assumption:** a coastal tract is one with any NRI coastal-flood exposure (`CFLD_EXPP > 0`). That
gives 182 tracts and 648,856 people.
Destinations are clean-capacity EVAC/BOTH buildings.

| Measure | Value |
|---|---:|
| Carless households | 15,066 |
| Households with a car | 226,251 |
| **Car households per carless household** | **15.0** |
| Tracts with < 2 car households per carless | **1**: 13051001200 (Savannah), 391 carless vs 335 car households (0.86); nearest wheelchair-yes shelter 1.3 km |
| Carless households living on the coastal-flood layer (exposure-weighted) | 3,776 |
| Median km to nearest usable shelter | 4.6 |
| Median km to nearest wheelchair-yes shelter | 7.5 |
| **Median km to nearest wheelchair-yes shelter not recorded in surge area** | **40.3** |
| Tracts > 10 km from a wheelchair-yes shelter | 67, holding 3,311 carless households |

The ratio is car *households* per carless household, not vehicles per carless household, so it is
not comparable to the prework's 29 vehicles per household. By that measure ride-matching capacity
exists almost everywhere on the coast. Hypothesis: the destination is the tighter constraint. In the coastal
counties, 13 of 17 wheelchair-yes usable shelters are recorded inside the surge/SLOSH area and 1 is
unrecorded. A wheelchair user leaving the coast has a recorded-accessible, not-recorded-in-surge
shelter about 40 km away (median).

Per county (`out/coastal_by_county.csv`): Chatham 7,533 carless households (12.5 car hh each), Glynn
2,044 (15.7; median 10.4 km to wheelchair-yes), Liberty 1,070 (21.5; 12.5 km), Camden 1,149
(16.2; 10.8 km), McIntosh 395 (15.1; 15.2 km). Tract list: `out/coastal_tracts.csv`.

## 4. Medically dependent (`medical.py`)

| Measure | Value |
|---|---:|
| Medical-needs shelters (`is_medical`) | 14, in 9 counties |
| Their seats (all pass the capacity rules) | 4,594 |
| Power-dependent Medicare beneficiaries (emPOWER) | 92,567 |
| **Power-dependent per medical seat, statewide** | **20.1** |
| Counties with no medical-needs shelter | 150, holding 84,485 power-dependent residents |
| Median tract → medical shelter | 45.7 km |
| Median coastal tract → medical shelter | 76.5 km |
| Georgians > 50 km from a medical shelter | 4,538,086 (700,996 aged 65+) |

Seats are concentrated, not distributed. Candler County (Metter, 109 power-dependent residents) has 5 of the
14 shelters and 1,328 of the 4,594 seats. Cobb's one medical shelter (1,398 seats) carries the name
"Southern Polytechnic State University" (`out/numbers.json → medical.medical_shelter_rows`); that
institution has since merged into Kennesaw State (from memory, not checked), which makes this row a
Maps-grounding candidate. Counties: `out/medical_by_county.csv`.

**Nursing homes in exposed tracts** (CMS, 356 facilities, 39,494 beds; nearest-centroid tract).
High-hurricane means `HRCN_AFREQ` in Georgia's top quintile (≥ 0.1265, an assumption). All 25
coastal-flood facilities are also high-hurricane.

| Measure | Value |
|---|---:|
| Facilities in coastal-flood tracts | 25 (2,599 beds) |
| Facilities in high-hurricane tracts | 110 (11,295 beds) |
| Median km from these to a medical-needs shelter | 75.9 (all facilities: 52.1) |
| Of these, > 50 km from a medical-needs shelter | 77 |

The farthest (`out/care_facilities_exposed.csv`): Senior Care Center St Marys (Camden; tract 51%
coastal-flood exposed) is 185 km away, Folkston Park (Charlton) 173 km, and four Valdosta nursing
homes about 163 km. Valdosta lies on the I-75 segment where GDOT measured Milton's 280% northbound
surge.

## 5. Equity audit (`equity.py`)

Race is used only to audit the output. Source: ACS 2022 5-year B03002 for all 2,796 Georgia tracts
(`fetch_acs_race.py` → `data/ga_tract_race_acs2022.csv`). It is never an input to any ranking.

Audited list: the top 20 coastal tracts by **carless households living on the coastal-flood layer**
(`out/top20_coastal_carless.csv`). Counterfactual: the top 20 by raw carless count, which overlaps
the first list in 10 of 20 tracts.

`out/equity_audit.csv`, shares of population:

| Tract set | Tracts | Pop | White NH | Black NH | Hispanic | Asian NH | Other |
|---|---:|---:|---:|---:|---:|---:|---:|
| Georgia | 2,796 | 10,722,325 | 50.8% | 31.1% | 10.1% | 4.3% | 3.8% |
| All coastal-flood tracts | 182 | 660,685 | 55.6% | 30.5% | 7.3% | 2.0% | 4.6% |
| Top 20, exposure-weighted carless | 20 | 80,434 | 41.5% | **45.1%** | 6.7% | 1.7% | 5.0% |
| Top 20, raw carless count | 20 | 79,379 | 35.8% | **50.3%** | 7.9% | 2.1% | 3.9% |

The coastal tracts as a whole look like the state. The tracts ranked by people who cannot drive out
are disproportionately Black: 45–50% against 31%. The variables that drove the ranking are physical
(vehicle access, flood exposure), so this is the correlation the README warns about, surfacing in
the output. It is not an input. The exposure weighting moves the list toward the state mix compared
with raw counts. Neither ranking uses recorded accessibility, so this list does not reward places
with better clerical practice.

## Caveats

- Straight-line distance from tract centroids, not drive time.
- `vulnerability_tracts.total_pop` sums to 10,516,579 while ACS 2022 B03002 sums to 10,722,325. In
  tract 13001950201, `total_pop` is 2,276 while `svi_total_pop` and ACS 2022 are both 2,392.
  Hypothesis: `total_pop` comes from a different ACS release. Rates here use `total_pop`; audit
  shares use B03002.
- ACS margins of error on carless households are large in many tracts (project checklist). The top-20
  list is a single ranking; robustness across MOE draws is not done here.
- The coastal-tract rule (`CFLD_EXPP > 0`) includes tracts with tiny exposure (Folkston's is 0.3%).
  The exposure-weighted counts carry that information; the tract list does not.
- Shelter records are a registry and never show live status. This is planning, not operations.

Sources: [GDOT via AllOnGeorgia](https://allongeorgia.com/georgia-state-news/georgia-dot-significant-increases-in-traffic-volumes-seen-on-georgia-interstates-as-hurricane-milton-approaches-floridas-west-coast/) ·
[WSB-TV](https://www.wsbtv.com/news/local/atlanta/hurricane-milton-traffic-along-i-75-up-280-people-evacuate-florida/5FTZL53MWRGIVOQ7AN7R7UPT6M/) ·
[CBS, Irma shelter count](https://www.cbsnews.com/amp/texas/news/florida-officials-127000-have-taken-refuge-from-hurricane-irma) ·
[ACS 2022 summary file](https://www2.census.gov/programs-surveys/acs/summary_file/2022/table-based-SF/)
