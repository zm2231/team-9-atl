# Origin → route → host: Georgia as receiving state, by storm scenario

For each storm scenario: who leaves and from where, which Georgia route they take, which host
counties' clean shelter capacity they use, and which counties run out first. Script:
`scenarios.py` (it also runs as the last step of `run.sh`). Outputs: `out/scenario_summary.csv`,
`out/scenario_host_fill.csv`, `out/scenario_origins.csv`, `out/scenario_storms.csv`, and
`out/numbers.json → scenarios`. Capacity follows the cleaning rules in [README.md](README.md).

Inputs beyond the snapshot. `EXTDATA` overrides the root (default `~/work/extdata`):

- NOAA IBTrACS v04r01, North Atlantic, storms within 300 km of Georgia (`ibtracs/`). Cite Knapp et
  al. 2010 and Gahtan et al. 2024, doi:10.25921/82ty-9e16. 2026 tracks are provisional.
- Georgia DOT hurricane evacuation routes and the I-16 contraflow route (`gdot_evac/`), the official
  corridor layer. Source: Georgia Department of Transportation (GDOT) EGIS, Office of Transportation
  Data. No licence is stated; the event organizers cleared Georgia state agency data for use with
  attribution on 2026-10-27.
- US Census Bureau TIGER/Line 2023 primary and secondary roads, Georgia
  (`tiger_roads/tl_2023_13_prisecroads.shp`, public domain), only where the GDOT layer has no route:
  I-75 north of Macon and I-20.
- GEMA I-16 contraflow intersections (`gema/contraflow_intersections.geojson`). Source: Georgia
  Emergency Management and Homeland Security Agency (GEMA/HS); cleared with attribution as above.
- Origin populations come from the Florida, South Carolina and Georgia snapshots (`vulnerability_tracts`,
  `power_dependent_counties`).

## Structural facts (measured)

- **The Georgia coast cannot shelter itself.** The 6 coastal counties (Chatham, Bryan, Liberty,
  McIntosh, Glynn, Camden) hold 543,194 people and have 23 usable evacuation shelters with 10,987
  clean seats. 14 of those shelters are recorded inside the surge/SLOSH area. For comparison, Georgia
  ordered about 540,000 coastal residents out during Irma in 2017
  (Transport Topics, 11 Sep 2017, [reposted](https://www.wvtrucking.com/press/transport-topics/3081-traffic-nightmare-as-more-than-1-million-flee-irma-in-florida-georgia)).
- **Medical-needs seats are in a handful of inland counties.** Candler County (Metter, on I-16) has 5
  of Georgia's 14 medical-needs shelters and 1,328 of its 4,594 medical seats. Every route out of the
  coast reaches the same four medical counties: Candler 1,328, Bulloch 737, Sumter 200, Laurens 150.
- **The I-75 route has a single medical-needs shelter: Cobb, 1,398 seats. Cobb's shelters sit
  391 km (capacity-weighted) from the Florida line.** I-20 from Augusta has one: Columbia, 504.

## Why these four scenarios (IBTrACS)

Storms since 1950 at hurricane strength within 300 km of Georgia: 57. **Assumption:** each is
classified by its first hurricane-strength point over US mainland or Keys land (`DIST2LAND = 0`,
lat ≥ 24.5, and lon ≤ −80 or lat ≥ 30). The box edges are in `scenarios.py: LANDFALL_CLASS`.

| Class | Storms | Examples |
|---|---:|---|
| (a) Georgia coast landfall | 0 | none since 1950; 5 hurricanes came within 100 km offshore: Matthew 2016, Charley 2004, Bob 1985, David 1979, Able 1952 |
| (b) NE / east Florida | 4 | Jeanne 2004, Erin 1995, David 1979, Dora 1964 |
| (c) Florida west coast / Big Bend | 10 | Debby, Helene, Milton (2024), Idalia 2023, Ian 2022, Hermine 2016, Charley 2004, … |
| (d) Carolinas | 18 | Isaias 2020, Dorian 2019, Matthew 2016, Hugo 1989, Hazel 1954, … |
| Gulf: Panhandle or west | 15 | Sally 2020, Michael 2018, Ivan 2004, Opal 1995, … |
| South Florida / Keys | 4 | Irma 2017, Irene 1999, Donna 1960, King 1950 |
| No US hurricane landfall | 6 | Ophelia 2005, Bob 1985, … |

Scenario (c) is the most frequent recent pattern, with 6 of its 10 storms since 2016. Scenario (a)
rests on near misses, not on landfalls. Classification uses first landfall only, so David 1979 counts
as (b) even though it later struck near Savannah. Full list: `out/scenario_storms.csv`.

## Routes (assumption: each scenario's flow uses one route set)

| Scenario | Origin (counties) | Georgia route | Host exclusions | Fill starts at |
|---|---|---|---|---|
| (a) Atlantic hit on GA coast | 6 GA coastal counties | GDOT hurricane evacuation network (98 segments, incl. I-16 SR 404) + I-16 contraflow | the 6 origin counties | origin population centroid |
| (a′) same, wider exclusion | same | same | all 12 counties with NRI coastal-flood exposure | same |
| (b) NE Florida / Jacksonville | Nassau, Duval, St Johns, Flagler, plus the 6 GA coastal counties (assumption: as in Irma 2017, Georgia's coast is ordered out too) | GDOT network | the 6 GA coastal counties | origin population centroid |
| (c) FL west coast, Milton-type | Pinellas, Hillsborough, Pasco, Manatee, Sarasota, Hernando, Citrus | I-75: GDOT SR 401 to Macon + TIGER I-75 north of Macon (segment centroids at or above 32.84° N) | none | I-75 at the Florida line |
| (d) Carolinas | SC: Beaufort, Jasper, Colleton, Charleston, Dorchester, Berkeley, Georgetown, Horry | TIGER I-20, segment centroids east of 84.40° W (not in the GDOT layer) | none | I-20 at the SC line |

`route_source` in `out/scenario_summary.csv` names the layer each scenario uses. A host shelter is
any usable shelter within 15 km of the scenario's route lines. `route_contraflow_intersections`
counts GEMA I-16 contraflow intersections within 1 km of the route: all 32 for (a), (a′) and (b),
none for (c) and (d).

The hand-drawn corridors used in the README sit close to both layers. GDOT I-75 vertices south of
Macon are within a median 1.8 km (max 5.7 km) of the I-75 south polyline, and TIGER's within 1.8 km
(max 5.8 km). For I-16 the medians are 2.8 km (GDOT) and 3.0 km (TIGER), both max 7.6 km.

The SR 401 = I-75 and SR 404 = I-16 reading of GDOT route ids is from GDOT's route numbering. It
matches the geometry: Florida line to Macon, and Savannah to Macon.

## Assumptions (all labelled, low / base / high)

| Parameter | Low | Base | High |
|---|---:|---:|---:|
| Residents of origin counties who leave | 20% | 35% | 50% |
| Share going to Georgia hosts: GA coast origins | 60% | 75% | 90% |
| … NE Florida | 20% | 35% | 50% |
| … Florida west coast | 5% | 15% | 30% |
| … Carolinas | 3% | 8% | 15% |
| Car-owning evacuees using a public shelter (Irma anchor ≈ 2%, see README) | 2% | 5% | 10% |
| Carless Georgian evacuees using a public shelter | 30% | 50% | 70% |

Further assumptions:

- **Carless households.** People in carless households are `households_no_vehicle` × tract
  household size. Carless Georgians are assumed to reach inland hosts on public transport. Carless
  out-of-state residents are assumed not to arrive in Georgia, and they are left out of every
  arrival count (`carless_out_of_state_not_arriving`; 9,914 in (b) base). Out-of-state 65+ and
  power-dependent arrivals are scaled by their county's car-owning share, on the assumption that
  they are carless at the county's average rate. Hypothesis: the real rate for older and disabled residents is
  likely higher, so these arrival counts lean high.
- **Host order.** Evacuees fill host counties nearest-first. The order is each county's
  capacity-weighted straight-line distance from the entry point. This tests the hosts closest to the
  threat; it is not a forecast of where people go.
- **Seat types.** General seekers fill only non-medical shelters. Medical-needs seats are compared
  separately against power-dependent arrivals. Power-dependent counts are a ceiling, because not
  every power-dependent person needs a medical shelter.
- **Not modelled.** Host counties' own residents, counties also inside the storm's wind field, and
  hotels.

## Results (`out/scenario_summary.csv`)

| Scenario | Level | Into GA hosts | Shelter seekers | Route general seats | Load | Counties filled | First full | Farthest host used | Power-dependent arriving | Medical seats on route | per seat |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| (a) GA coast | low | 65,183 | 2,518 | 162,967 | 1.5% | 1 | Long | 58 km | 524 | 2,415 | 0.22 |
| | base | 142,588 | 11,398 | 162,967 | 7.0% | 4 | Long | 77 km | 1,146 | 2,415 | 0.47 |
| | high | 244,437 | 34,201 | 162,967 | 21.0% | 14 | Long | 117 km | 1,964 | 2,415 | 0.81 |
| (a′) wider exclusion | base | 142,588 | 11,398 | 150,737 | 7.6% | 3 | Evans | 98 km | 1,146 | 2,415 | 0.47 |
| | high | 244,437 | 34,201 | 150,737 | 22.7% | 10 | Evans | 128 km | 1,964 | 2,415 | 0.81 |
| (b) NE Florida + GA coast | low | 118,053 | 3,575 | 162,967 | 2.2% | 2 | Charlton | 105 km | 1,031 | 2,415 | 0.43 |
| | base | 304,503 | 19,494 | 162,967 | 12.0% | 7 | Charlton | 138 km | 2,701 | 2,415 | **1.12** |
| | high | 574,875 | 67,245 | 162,967 | 41.3% | 28 | Charlton | 214 km | 5,138 | 2,415 | **2.13** |
| (c) FL west coast | low | 38,859 | 777 | 194,688 | 0.4% | 0 | none | 23 km | 388 | 1,398 | 0.28 |
| | base | 204,008 | 10,200 | 194,688 | 5.2% | 3 | Lowndes | 97 km | 2,035 | 1,398 | **1.46** |
| | high | 582,880 | 58,288 | 194,688 | 29.9% | 11 | Lowndes | 306 km | 5,813 | 1,398 | **4.16** |
| (d) Carolinas | low | 8,291 | 166 | 144,899 | 0.1% | 0 | none | 7 km | 73 | 504 | 0.14 |
| | base | 38,691 | 1,935 | 144,899 | 1.3% | 0 | none | 7 km | 340 | 504 | 0.68 |
| | high | 103,635 | 10,364 | 144,899 | 7.2% | 0 | none | 7 km | 912 | 504 | **1.81** |

No scenario exhausts its route's general seats, even at high (`unplaced_seekers` = 0 everywhere).

**What runs out first** (`out/scenario_host_fill.csv`, counties with their general seats and distance
from the entry point):

- **(a) GA coast:** Long (900 seats, 41 km), Wayne (2,499, 58 km), Effingham (4,707, 64 km) and Evans
  (2,890, 73 km) fill at base. Long, Wayne and Effingham are among the 12 counties with coastal-flood
  exposure. If they are unavailable (a′), the load moves to Evans, Tattnall and Bulloch, 73–89 km
  inland.
- **(b) NE Florida:** Charlton (400 seats, 73 km from the origin centroid) and Brantley (2,629) fill at
  low. At base, Pierce, Ware (8,810), Wayne, Long and Clinch fill too.
- **(c) Milton-type:** Lowndes, the first Georgia county on I-75, has 1,379 general seats and fills at
  base, followed by Brooks (273) and Cook (2,305). At high, the fill runs through Tift, Turner, Dooly,
  Houston and Peach to Bibb (Macon, 26,728), Jones and Monroe, 277 km in.
- **(d) Carolinas:** Richmond (Augusta, 16,746 seats) absorbs every level on its own.

## What this says (hypotheses, from the numbers above)

1. **General seats hold. Medical seats do not.** Even the high scenarios load the route's general
   seats at 41% or less. In (b) and (c), power-dependent arrivals exceed the medical-needs seats on
   the route from the base scenario up. (c) puts 2,035 power-dependent Floridians (base) on a route
   whose only medical shelter is in Cobb, 391 km past the Florida line.
2. **The pressure lands on small counties at the door.** Every first-full county is small and close
   to the threat: Long, Charlton, Lowndes. A planner's August question is about those few counties
   and the medical shelters at Metter and Statesboro. It is not about statewide totals.
3. **Scenario (b) is the double hit.** Jacksonville evacuees and the Georgia coast compete for the
   same southeast Georgia hosts and the same four medical counties (2.1 power-dependent per seat at
   high).

## Storm library (`storm_library.py`, `out/storm_library.csv`)

One row per Atlantic storm whose track came within 800 km of Georgia (IBTrACS v04r01): 731 storms,
1851-2026. **Assumption:** origin class is the first US mainland or Keys landfall at tropical-storm
strength (34 kt or more), in the same boxes as the scenarios above (`common.py: LANDFALL_CLASS`).

| Origin class | Storms | Since 1950 | With a Georgia lead time | Median watch lead (h) | Median warning lead (h) |
|---|---:|---:|---:|---:|---:|
| (a) Georgia coast | 19 | 5 | 0 | | |
| (b) NE / east Florida | 41 | 19 | 2 | 39 | 27 |
| (c) Florida west coast / Big Bend (I-75) | 75 | 34 | 9 | 40 | 25 |
| (d) Carolinas | 120 | 67 | 2 | 41 | 32 |
| Gulf: Panhandle or west | 192 | 92 | 3 | 32 | 23 |
| South Florida / Keys | 62 | 23 | 2 | 37 | 25 |
| No US landfall | 220 | 119 | 0 | | |

**Warning lead time (our calculation, from NWS VTEC and NHC best track).** For each storm since 2008,
hours from the first NWS watch, and the first warning, for any Georgia zone (coastal or inland) to the
first hour tropical-storm winds (the best-track R34 radius) reach Georgia. Across the 18 storms with a
Georgia watch, the median is 39 h (23 to 50 h). Examples: Ian 50/32, Michael 49/36, Milton 49/25,
Idalia 41/35, Helene 40/28, Matthew 40/28, Irma 38/26, Debby 38/26, Isaias 2026 27/27, Andrea 23/12
(watch/warning hours). NHC's coastal watches alone understate inland lead time for Gulf storms
(Michael: 25 h coastal against 49 h with inland VTEC watches). The class medians rest on 2 to 9
storms each and are not a forecast.

**Evacuation orders** (`data/clean/out/evac_orders.parquet`, cited governor releases). Mandatory
orders took effect 35 h (Irma 2017) and 41 h (Dorian 2019) before Georgia tropical-storm winds;
I-16 contraflow began 35 h and 21 h before. Matthew 2016's release gives only the date, which puts
its mandatory order 9 to 33 h ahead. **Simulator default (assumption):** order effective 35 to 41 h
before tropical-storm winds, observed in two Atlantic storms. No coastal mandatory order was found
for the Gulf storms (Michael, Helene, Milton, Isaias 2026); that is unverified.

**Power outages** (EAGLE-I, Brelsford et al. 2024, ORNL / DOE CESER, CC BY 4.0, through the grid
analysis `analysis/grid/out/county_storm_outages.parquet`; `GRID_OUT` overrides the path). Georgia
counties with at least 10% of customers out: Helene 109 counties (43,245 power-dependent residents),
Michael 81 (21,392), Idalia 44, Debby 28, Ian 9, Milton 7, Dorian 5. Matthew and Irma are left out of
these counts because EAGLE-I has no data-quality index before 2018. The widest outages came from Gulf
storms and reached far inland, so the power-dependent demand trigger is county outage share, not
coastal zone.

## Corridor load vs capacity (`corridor_vc.py`, `out/corridor_vc.json`)

A peak-hour volume-to-capacity ratio for I-75 S (FL line to Macon), I-16 (with contraflow) and I-95,
for three storm origins and the low / base / high cases. It is meant to scale live drive times in
the scenario tool. **Every row has status `assumption`.** Volumes come from the scenario populations
above (`out/scenario_origins.csv` and the scenario rates in `out/numbers.json`), and every parameter
that turns them into vehicles per hour is assumed:

| Origin | Scenario used | Leaving vehicles counted |
|---|---|---|
| `gulf` | (c) Florida west coast, up I-75 | Florida residents with a car whose destination is Georgia |
| `florida_peninsula` | (b) NE Florida, Georgia coast also ordered out | as above for Florida, plus every Georgia coastal resident with a car who leaves |
| `atlantic_ga` | (a) Georgia coast | every Georgia coastal resident with a car who leaves |

Georgia residents count wherever they are headed, because they drive Georgia roads either way.
Carless residents are not on the road.

| Parameter (assumption) | Low | Base | High |
|---|---:|---:|---:|
| Persons per evacuating vehicle | 2.5 | 2.0 | 1.6 |
| Share of vehicles in the peak hour | 0.06 | 0.09 | 0.12 |
| Flow per lane, vehicles per hour | 1,800 | 1,500 | 1,200 |

The low case pairs the low scenario volume with the capacity-friendly end of each bracket, and the
high case the reverse, so the range is wide by construction. Lanes per direction are assumed, not
measured: I-75 S 3, I-95 3, I-16 2 plus the 2 reversed eastbound lanes under contraflow (4). The
corridor share of each origin's vehicles is also assumed: Chatham and Bryan 100% on I-16; Liberty
50% on I-95 then I-16; McIntosh and Glynn 40%; Camden 30%; NE Florida 40% on I-95 then I-16, 40% on
I-10 to I-75, and 20% elsewhere; Florida west coast 100% on I-75. A vehicle that uses I-95 and then
I-16 counts on both. Only evacuation traffic is counted, because live drive times already include
normal traffic.

| V/C | Low | Base | High |
|---|---:|---:|---:|
| `gulf` on I-75 S | 0.17 | 2.04 | 12.14 |
| `florida_peninsula` on I-16 | 0.33 | 1.50 | 5.08 |
| `florida_peninsula` on I-95 | 0.17 | 0.94 | 3.61 |
| `florida_peninsula` on I-75 S | 0.09 | 0.65 | 2.75 |
| `atlantic_ga` on I-16 | 0.26 | 1.01 | 3.01 |
| `atlantic_ga` on I-95 | 0.07 | 0.29 | 0.86 |

Corridors an origin does not use under these shares are 0. A ratio above 1 means peak demand
exceeds capacity: the road carries its capacity and departures spread over more hours, so a delay
multiplier built on it needs a ceiling. Per-row vehicles, peak-hour vehicles and capacity are in
`out/numbers.json` under `corridor_vc`.

## Limits

- Straight-line distances. Routes are a buffer, not a network flow. Road capacity is only the
  assumed peak-hour ratio above; there is no network assignment.
- The fill is nearest-first by construction, so "first full" depends on the entry point chosen.
- Every share is an assumption. GDOT's Milton counts (I-75 northbound +280%) confirm direction, not volume.
- Shelter records are a registry, not live status. This is planning, not operations.
