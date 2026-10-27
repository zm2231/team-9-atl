# County grid reliability in hurricanes (Georgia, 159 counties)

Rates each Georgia county's electric power as HIGH, MEDIUM or LOW reliability in hurricanes, from what
recent storms actually did to it. The table feeds the power-dependent side of a preparation simulator:
where power-dependent residents lose power in a storm, and for how long. A second table holds the per-storm
county outages for Georgia's 159 and Florida's 67 counties.

```
uv run --project analysis/grid python analysis/grid/build_grid.py
uv run --project analysis/grid pytest analysis/grid/tests
```

Inputs are read from `~/work/extdata` and `~/work/c4data` (override with `GRID_EXTDATA`, `GRID_C4DATA`).
The build checks:
- 159 unique Georgia counties, and 226 counties × every listed storm in the storm table;
- no unmatched EIA county names;
- UNKNOWN means no hit storm;
- every censored restore time that feeds a tier is at least the LOW threshold;
- every non-key column has `_status` and `_rule` companions, with values from the vocabulary in `build_grid.py`.

The test recomputes the published EAGLE-I storm summary (`ga_fl_storm_outage_summary.parquet`, 9 storms × 226
counties) from the 15-minute file with that summary's own windows and requires every field to match. Every
number below is in `out/summary.json`, written by the same run, which also records the SHA-256 of each input.

## Outputs

| File | Rows | Key |
|---|---|---|
| `out/county_grid_reliability.parquet` / `.csv` | 159 | `fips_code` |
| `out/county_storm_outages.parquet` | 6,102 (226 counties × 27 storms; GA 4,293, FL 1,809) | `fips_code`, `sid` |
| `out/summary.json` | – | storm list, tier counts, sensitivity, cross-checks, rule text |

Every non-key column `x` has `x_status` and `x_rule`, or shares them with a group named in
`PROVENANCE_GROUPS`. For example, `tier_composite_score` uses the `tier_alt_terciles_*` pair, and
`peak_customers_out` and the other EAGLE-I fields use `eaglei_record_*`. Status is one of `recorded`,
`derived`, `low_data`, `suspect`, `unrecorded` or `baseline_only`. The rule is a key of `RULES`, whose text
is also in `summary.json`. Precedence: `unrecorded` > `suspect` > `low_data` > `derived`.

## Storm list and windows

**Rule (`ibtracs_storm_list`).** Every IBTrACS v04r01 North Atlantic storm (main track) from seasons 2018–2025
with a track point within **250 km of the Georgia state polygon** (`dist_ga_km` in the IBTrACS extract). EAGLE-I
ends on 2025-12-31, so the two 2026 storms in the extract are out. The same storms apply to Florida's
counties; Florida-only storms that never came within 250 km of Georgia are not in the list (Milton 2024 is
one).

**Window.** Local Eastern dates, from the date of the storm's first track point within 800 km of Georgia's
centroid to the date of its last such point plus 7 days. The peak is searched only during passage: from
the window start to 24 h after the last track point within 800 km. Without that limit, the 7-day tail
attributes ordinary summer thunderstorm outages to weak storms. Hours above 10% out use the whole window.
Restoration is searched to 7 days after the window end.

| Storm | Season | IBTrACS SID | Closest to GA (km) | Max wind (kt) | Window (local) | Peak searched until (UTC) | GA counties hit | FL counties hit |
|---|---|---|---|---|---|---|---|---|
| Alberto | 2018 | 2018146N19273 | 99.7 | 55 | 2018-05-27 – 2018-06-06 | 2018-05-30 15:00 + 24 h | 2 | 1 |
| Florence | 2018 | 2018242N13343 | 35.4 | 130 | 2018-09-13 – 2018-09-24 | 2018-09-17 21:00 + 24 h | 6 | 0 |
| Michael | 2018 | 2018280N18273 | 0 | 140 | 2018-10-09 – 2018-10-18 | 2018-10-12 03:00 + 24 h | 81 | 17 |
| Dorian | 2019 | 2019236N10314 | 134.8 | 160 | 2019-09-02 – 2019-09-13 | 2019-09-06 12:30 + 24 h | 5 | 0 |
| Nestor | 2019 | 2019291N22264 | 0 | 50 | 2019-10-18 – 2019-10-27 | 2019-10-20 18:00 + 24 h | 3 | 1 |
| Bertha | 2020 | 2020148N32281 | 141.2 | 45 | 2020-05-27 – 2020-06-04 | 2020-05-28 09:00 + 24 h | 5 | 0 |
| Fay | 2020 | 2020188N28271 | 0 | 50 | 2020-07-05 – 2020-07-16 | 2020-07-09 15:00 + 24 h | 8 | 3 |
| Isaias | 2020 | 2020211N13306 | 127.1 | 80 | 2020-08-02 – 2020-08-11 | 2020-08-04 09:00 + 24 h | 7 | 0 |
| Omar | 2020 | 2020244N30279 | 91.1 | 35 | 2020-08-30 – 2020-09-08 | 2020-09-01 06:00 + 24 h | 3 | 1 |
| Sally | 2020 | 2020256N25281 | 0 | 95 | 2020-09-12 – 2020-09-25 | 2020-09-18 06:00 + 24 h | 18 | 10 |
| Beta | 2020 | 2020261N21265 | 97 | 55 | 2020-09-24 – 2020-10-02 | 2020-09-25 06:00 + 24 h | 4 | 2 |
| Delta | 2020 | 2020279N16284 | 64.2 | 120 | 2020-10-10 – 2020-10-18 | 2020-10-11 18:00 + 24 h | 6 | 1 |
| Zeta | 2020 | 2020299N18277 | 33.9 | 100 | 2020-10-28 – 2020-11-05 | 2020-10-29 18:00 + 24 h | 56 | 3 |
| Eta | 2020 | 2020306N15288 | 10.1 | 130 | 2020-11-11 – 2020-11-20 | 2020-11-13 12:00 + 24 h | 4 | 0 |
| Claudette | 2021 | 2021169N23268 | 0 | 40 | 2021-06-19 – 2021-06-28 | 2021-06-21 12:00 + 24 h | 2 | 2 |
| Danny | 2021 | 2021179N30287 | 41.2 | 40 | 2021-06-28 – 2021-07-05 | 2021-06-29 00:00 + 24 h | 1 | 1 |
| Elsa | 2021 | 2021182N09317 | 0 | 75 | 2021-07-06 – 2021-07-15 | 2021-07-09 00:00 + 24 h | 6 | 8 |
| Fred | 2021 | 2021222N14301 | 0 | 55 | 2021-08-15 – 2021-08-25 | 2021-08-18 12:00 + 24 h | 8 | 10 |
| Ida | 2021 | 2021239N17281 | 78.1 | 130 | 2021-08-28 – 2021-09-08 | 2021-09-01 15:00 + 24 h | 9 | 2 |
| Mindy | 2021 | 2021252N28273 | 0 | 50 | 2021-09-08 – 2021-09-16 | 2021-09-10 03:00 + 24 h | 3 | 8 |
| Colin | 2022 | 2022183N32280 | 13.7 | 35 | 2022-07-01 – 2022-07-09 | 2022-07-02 18:00 + 24 h | 0 | 1 |
| Ian | 2022 | 2022266N12294 | 179.7 | 140 | 2022-09-28 – 2022-10-08 | 2022-10-01 06:00 + 24 h | 8 | 29 |
| Nicole | 2022 | 2022311N21293 | 0 | 65 | 2022-11-09 – 2022-11-18 | 2022-11-11 18:00 + 24 h | 6 | 10 |
| Idalia | 2023 | 2023239N21274 | 0 | 115 | 2023-08-29 – 2023-09-07 | 2023-08-31 15:00 + 24 h | 40 | 19 |
| Debby | 2024 | 2024216N20284 | 0 | 70 | 2024-08-04 – 2024-08-16 | 2024-08-09 09:00 + 24 h | 26 | 19 |
| Helene | 2024 | 2024268N17278 | 0 | 120 | 2024-09-26 – 2024-10-05 | 2024-09-28 18:00 + 24 h | 107 | 36 |
| Chantal | 2025 | 2025185N30280 | 193.7 | 50 | 2025-07-04 – 2025-07-14 | 2025-07-07 12:00 + 24 h | 3 | 2 |

## Method

**1. Storm outages per county (EAGLE-I).** The metrics are recomputed from the 15-minute county file with the
method of the published EAGLE-I storm summary:
- **Gaps and nulls.** A timestamp with no Georgia or Florida record at all is a collection gap. A record
  with a null value is unknown. Both carry the county's last value forward; any other missing interval is 0.
- **Peak share** = peak customers out / EAGLE-I 2024 total customers, capped at 1.
- **`hours_above_10pct`** = hours with customers out ≥ 10% of those customers.
- **`restore_90_hours`** = hours from the peak to the first interval at or below 10% of the peak.

A storm row is a **hit** when the capped peak share is at least 0.10, and only hit rows feed the tiers. All
rows stay in `county_storm_outages`, with the reason in `used_in_tier_rule`:
- **`prior_storm_carryover`** (12 rows): a would-be hit whose peak precedes the storm's first track point
  within 800 km, or whose county already had ≥ 50% of that peak out when the window opened. The outage is
  an earlier event still being restored. These rows are `suspect` and not used.
- **Capped shares** (15 hits, 11 of them Georgia, all Helene except one Debby row): the uncapped share
  exceeds 1. They are kept, capped and marked `suspect`, and so is their `hours_above_10pct` (same denominator).
- **Censored restore** (3 hits: Helene in Atkinson, Coffee, Jeff Davis): outages never fell to 10% of peak
  within the search. `restore_90_hours` is then the hours from the peak to the end of the search, a lower
  bound (rule `eaglei_restore_censored_lower_bound`).
- **Non-hits:** storms below 0.10 peak share did not test the county's grid, so they are not used.

613 storm rows are hits: 427 in Georgia, 186 in Florida.

Per Georgia county, over its hit storms, the script computes the median and the worst of peak share,
`hours_above_10pct` and `restore_90_hours`, plus `n_storms_hit` and `storms_hit`.
- **`low_data`:** a county with exactly one hit storm.
- **`suspect`:** a share or hours metric fed by a suspect row (the worst row for worst-case metrics, any hit
  row for medians). The tier statuses follow the share metric they are built on.
- **`peak_share_max_2018plus`:** the worst capped share from any usable listed storm, hit or not.

**2. Baseline reliability (EIA-861).** Each county is mapped to the utilities whose 2024 service territory
lists it. County names are matched to FIPS case-insensitively, and none are unmatched.
- **SAIDI per utility:** IEEE SAIDI with and without major event days (MED), averaged over its 2018–2024
  years where both are filed. 2019 drops out because this EIA-861 extract has no 2019 SAIDI with MED for any
  Georgia utility.
- **County weight:** utility mean customers / number of Georgia counties it serves. This approximates the
  utility's customers in that county under an even-spread assumption, because EIA does not publish
  customers by county.
- **`storm_multiplier`** = weighted SAIDI with MED / without MED.

Of 97 Georgia utilities in the 2024 territory, only 31 file usable SAIDI for 2018–2024. The county value
covers only the reporting utilities (`n_utilities_reporting` of `n_utilities`), and its status is
`low_data` when any serving utility does not report. 158 counties have a value; 53 have all serving
utilities reporting. The median multiplier is 3.41 (p10 2.71, p90 3.83).

**`baseline_tier` (secondary, all counties).** Terciles of the mean percent rank of weighted SAIDI with
MED and the storm multiplier: the top third is LOW, the bottom third HIGH. The status is `baseline_only`
and the rule text begins "Baseline only, no storm test". It never replaces `reliability_tier`.
- **Scope:** it is annual and utility-wide. The utility with the largest territory is Georgia Power (EIA
  utility 7140), the only investor-owned utility in the Georgia reliability extract. It appears in 155 of
  the 159 counties' territory lists (`eia_largest_territory` in `summary.json`).
- **Untested hypothesis:** county differences mostly reflect which EMCs and municipals share a county with
  Georgia Power.
- **Chatham has no baseline.** The 2024 EIA-861 territory lists only Canoochee EMC for Chatham, and
  Canoochee files no SAIDI. Georgia Power's 2024 territory list omits Chatham, Union, Towns and Fannin.

**3. Tiers.** The primary rule (`tier_fixed_thresholds`) uses fixed thresholds that an emergency manager can read:

- **LOW**: worst peak share ≥ 0.50 **and** worst hours to 90% restored ≥ 72. At least half the county
  lost power and full restoration took more than the 72-hour self-sufficiency horizon.
- **HIGH**: worst peak share < 0.25 **and** worst hours to 90% restored < 24.
- **MEDIUM**: otherwise.
- **UNKNOWN**: no hit storm. Never defaulted to a tier.

Two alternatives are reported per county for sensitivity:
- `tier_alt_terciles`: terciles of the mean percent rank of the two worst-case metrics.
- `tier_alt_median`: the same thresholds applied to medians across hit storms instead of worst cases.

`tier_stable` is true when all three rules agree.

**4. Power-dependent residents.** `power_dependent_dme` comes from the team's c4data Georgia
`power_dependent_counties` snapshot (emPOWER, 92,567 statewide). The live HHS emPOWER service reports a
different, higher total; the per-tier sums here use the snapshot.

## Results

| Tier | Counties | Power-dependent residents | Counties with one hit storm | Tier status `suspect` |
|---|---|---|---|---|
| LOW | 55 | 19,589 | 4 | 11 |
| MEDIUM | 75 | 51,730 | 20 | 0 |
| HIGH | 21 | 15,800 | 10 | 0 |
| UNKNOWN | 8 | 5,448 | – | – |

Tier status:
- 107 `derived`;
- 33 `low_data`;
- 11 `suspect` (worst share capped from above 1; all LOW either way);
- 8 `unrecorded` (UNKNOWN).

**5,448 of the 92,567 power-dependent residents (snapshot) live in UNKNOWN counties.** Zeta (2020) is the
storm that tested most of north Georgia and metro Atlanta: it hit 56 Georgia counties. Fulton, Cobb,
Gwinnett and Cherokee are MEDIUM on Zeta alone.

**Sensitivity.** Of 151 tiered counties, 63 keep the same tier under all three rules.
- **Terciles** change 39 counties: 7 LOW→MEDIUM, 30 MEDIUM→HIGH, 2 MEDIUM→LOW.
- **The median rule** changes 67: 34 LOW→MEDIUM, 12 LOW→HIGH, 21 MEDIUM→HIGH. Most LOW counties are LOW
  because of one storm (Helene), not repeatedly.
- **HIGH** is the same under all three rules (21 of 21), but 10 of the 21 rest on a single hit storm.

**EIA corroboration (weak).** The median storm multiplier rises with the EAGLE-I tier: HIGH 3.16,
MEDIUM 3.4, LOW 3.67 (UNKNOWN 2.87). This agrees in direction and comes from an independent source, but it
is utility-wide.

**Baseline tiers.** LOW 52 counties (17,516 power-dependent), MEDIUM 53 (15,761), HIGH 53 (57,341),
UNKNOWN 1 (Chatham, 1,949).

**Baseline vs storm tier.** Of 150 counties with both, 62 get the same tier. The baseline leans the same way
at the extremes but disagrees often, so treat it as a label, not a substitute.

| Storm tier | Baseline LOW | Baseline MEDIUM | Baseline HIGH | Baseline UNKNOWN |
|---|---|---|---|---|
| LOW | 26 | 23 | 5 | 1 (Chatham) |
| MEDIUM | 22 | 23 | 30 | – |
| HIGH | 2 | 6 | 13 | – |

The 8 storm-UNKNOWN counties split baseline HIGH 5, MEDIUM 1, LOW 2.

**LOW counties with the most power-dependent residents:**

| County | FIPS | Power-dependent | Hit storms | Worst peak share | Worst h to 90% restored (storm) | Worst h ≥10% out | Stable |
|---|---|---|---|---|---|---|---|
| Chatham | 13051 | 1,949 | Idalia, Helene | 0.73 | 135 (Helene) | 136.25 | no |
| Richmond | 13245 | 1,647 | Michael, Helene | 0.95 | 162.25 (Helene) | 211.5 | yes |
| Lowndes | 13185 | 1,160 | Idalia, Debby, Helene | 0.82 | 259.5 (Helene) | 216.5 | yes |
| Columbia | 13073 | 1,094 | Helene | 1.00 (suspect) | 143 (Helene) | 211.25 | yes |
| Glynn | 13127 | 907 | Idalia, Helene | 0.88 | 83.75 (Helene) | 92.25 | no |
| Coffee | 13069 | 720 | Michael, Idalia, Debby, Helene | 0.67 | ≥ 370.25 (Helene, censored) | 215 | no |
| Tift | 13277 | 608 | Michael, Idalia, Debby, Helene | 1.00 (suspect) | 230.25 (Helene) | 216.25 | no |
| Ware | 13299 | 598 | Michael, Idalia, Helene | 0.90 | 260.5 (Helene) | 215.75 | no |
| Pickens | 13227 | 562 | Delta, Zeta | 0.77 | 73.5 (Zeta) | 63.5 | no |
| Bulloch | 13031 | 550 | Michael, Idalia, Helene | 0.87 | 170 (Helene) | 183.25 | no |

**UNKNOWN.** The 8 untiered counties are Walker (1,280 power-dependent), Dougherty (1,109), Barrow (939),
Spalding (831), Catoosa (681), Crisp (314), Screven (163) and Early (131). No listed storm took 10% of their
customers out during passage. Their worst recorded share is at most 0.093 (median 0.076).

**OE-417 cross-check.** OE-417 has a single Georgia filing per storm window, each 34k–57k customers.
EAGLE-I's sum of Georgia county peaks is far larger: Zeta 1,052,816, Michael 423,588, Sally 140,259. The
OE-417 filings cover one utility's report, not the state, and there are no 2024 files, so OE-417 is not
used in the tiers.

## Caveats

- **The tier measures exposure plus grid.** A county in Helene's or Zeta's path is LOW or MEDIUM even if its
  utility restored fast relative to the damage.
- **Carried-forward values can stretch outages.**
  - **Nulls:** 204 of the 613 hits contain null-value intervals, at most 453 (about 113 hours) in one hit,
    and these carry the county's last value forward. This matches the published EAGLE-I summary but can
    lengthen hours and restore times where a feed stopped reporting during an outage.
  - **Zeros:** single-utility feed gaps that read as zero shorten them.
- **Windows are rule-based.**
  - **Truncated hours:** `hours_above_10pct` counts only inside the window, so Helene's longest outages
    (window ends 2024-10-05) are truncated.
  - **Overlaps:** Sally/Beta, Claudette/Danny and Ida/Mindy windows overlap. The passage-only peak and the
    carryover rule keep an outage from counting twice, but a residual from the earlier storm can still sit
    inside the later storm's `hours_above_10pct`.
- **Weak storms can still pick up convective outages.** A thunderstorm during passage can still count.
- **Shares are approximate.** The denominator is EAGLE-I's 2024 attributed customers.
- **Restore is relative to the county's own peak.** It is the time until outages fall to 10% of peak, not
  to 10% of customers.
- **Small numbers.** 34 of 151 tiered counties rest on one hit storm (33 `low_data`; Columbia is `suspect`,
  which takes precedence).
- **EIA weights are approximate.** They assume a utility's customers spread evenly across its counties.
  66 of 97 serving utilities file no SAIDI. `baseline_tier` is utility-wide context with no storm test.
- **Inputs can change.** The inputs are external files. `summary.json` records their SHA-256, so a refresh
  shows up as a hash change.
- **Planning only.** Historical outage patterns, not a forecast and not live status.

## Attribution

- Brelsford et al., EAGLE-I Recorded Electricity Outages, ORNL / DOE CESER, Scientific Data 2024,
  doi:10.6084/m9.figshare.24237376.v4, CC BY 4.0. Changes: filtered to Georgia and Florida, aggregated to
  storm windows and county summaries.
- NOAA International Best Track Archive for Climate Stewardship (IBTrACS) v04r01, Knapp et al. (2010, BAMS)
  and Gahtan et al. (2024), doi:10.25921/82ty-9e16. U.S. Government work.
- U.S. Energy Information Administration, Form EIA-861 (reliability and service territory), U.S. Government work.
- U.S. Department of Energy, Form OE-417 Electric Emergency Incident and Disturbance Reports, U.S. Government work.
- HHS emPOWER Program (ASPR/CMS), via the team's Georgia `power_dependent_counties` snapshot.
