# County grid reliability in hurricanes (Georgia, 159 counties)

Rates each Georgia county's electric power as HIGH, MEDIUM or LOW reliability in hurricanes, from what
recent storms actually did to it. The table feeds the power-dependent side of a preparation simulator:
where power-dependent residents lose power in a storm, and for how long.

```
uv run --project analysis/grid python analysis/grid/build_grid.py
```

Inputs are read from `~/work/extdata` and `~/work/c4data` (override with `GRID_EXTDATA`, `GRID_C4DATA`).
The script checks for 159 unique counties, 159 × 9 storm rows, and no unmatched EIA county names. It
also checks that UNKNOWN means no hit storm and that every Milton row before the cutoff is carryover. It
checks that every non-key column has `_status` and `_rule` companions with values from the vocabulary in
`build_grid.py`. Every number below is in `out/summary.json`, written by the same run, which also records
the SHA-256 of each input file.

## Outputs

| File | Rows | Key |
|---|---|---|
| `out/county_grid_reliability.parquet` / `.csv` | 159 | `fips_code` |
| `out/county_storm_outages.parquet` | 1,431 (159 counties × 9 storms) | `fips_code`, `storm` |
| `out/summary.json` | – | tier counts, sensitivity, cross-checks, rule text |

Every non-key column `x` has `x_status` and `x_rule`, or shares them with a group named in
`PROVENANCE_GROUPS`. For example, `tier_composite_score` uses the `tier_alt_terciles_*` pair, and
`peak_customers_out` and the other raw EAGLE-I fields use `eaglei_record_*`. Status is one of `recorded`,
`derived`, `low_data`, `suspect`, `unrecorded` or `baseline_only`. The rule is a key of `RULES`, whose text
is also in `summary.json`. Precedence: `unrecorded` > `suspect` > `low_data` > `derived`.

## Method

**1. Storm outages per county (EAGLE-I).** The source summary has one row per storm × county for nine named
storms. A storm row is *usable* when it is 2018 or later and is not Helene carryover, and a usable row is a
*hit* when the capped peak share is at least 0.10. Only hit rows feed the tiers. The other rows stay in
`county_storm_outages` with `used_in_tier = false` and the reason in `used_in_tier_rule`:

- Matthew 2016 and Irma 2017 are excluded: EAGLE-I has no data-quality index before 2018 and has known overcounts.
- 54 Georgia Milton rows have their peak before Milton arrived (2024-10-10 00:00 UTC). The Helene and
  Milton windows overlap, so these peaks are Helene outages still being restored. They are marked
  `suspect` and excluded. 14 of them would otherwise count as hits.
- Peak share = peak customers out / EAGLE-I 2024 total customers, capped at 1. Thirteen Helene rows exceed 1
  before capping; they are kept, capped and marked `suspect`. Their `hours_above_10pct` is also `suspect`
  because it uses the same denominator.
- Storms below 0.10 peak share did not test the county's grid, and time-to-restore on a 2% outage says
  nothing about hurricane resilience, so these rows are excluded.

Counties hit per storm: Michael 81, Dorian 5, Ian 9, Idalia 44, Debby 28, Helene 109, Milton 7.

Per county, over its hit storms, the script computes the median and the worst of: peak share,
`hours_above_10pct` (hours with ≥10% of customers out), and `restore_90_hours` (hours from peak until
outages fall to 10% of peak). It also records `n_storms_hit` and `storms_hit`. A county with exactly one hit
storm gets status `low_data`. A share or hours metric is `suspect` when a suspect row feeds it: the worst row
for worst-case metrics, any hit row for medians. The tier statuses follow the share metric they are built on.
`peak_share_max_2018plus` is the worst capped share from any usable storm,
hit or not, so untiered counties still show their worst recorded share.

**2. Baseline reliability (EIA-861).** Each county is mapped to the utilities whose 2024 service territory
lists it; county names are matched to FIPS case-insensitively, and none are unmatched. Each utility's IEEE SAIDI
with and without major event days is averaged over its 2018–2024 years where both are filed. 2019 drops
out because this EIA-861 extract has no 2019 SAIDI with MED for any Georgia utility. Utilities are then combined per county
with weight = utility mean customers / number of Georgia counties it serves. This approximates the
utility's customers in that county under an even-spread assumption; EIA does not publish customers by
county. `storm_multiplier` = weighted SAIDI with MED / without MED.

Of 97 Georgia utilities in the 2024 territory, only 31 file usable SAIDI for 2018–2024. The county value
therefore covers only the reporting utilities (`n_utilities_reporting` of `n_utilities`), and its status
is `low_data` when any serving utility does not report. 158 counties have a value; 53 have all serving
utilities reporting. The median multiplier is 3.41 (p10 2.71, p90 3.83).

**`baseline_tier` (secondary, all counties).** Terciles of the mean percent rank of weighted SAIDI with
MED and the storm multiplier: the top third is LOW, the bottom third HIGH. The status is `baseline_only`
and the rule text begins "Baseline only, no storm test". It gives every county with EIA data a labelled
value, including the storm-UNKNOWN counties, but it never replaces `reliability_tier`. It is annual and
utility-wide. The utility with the largest territory is Georgia Power (EIA utility 7140), the only
investor-owned utility in the Georgia reliability extract. It appears in 155 of the 159 counties'
territory lists (`eia_largest_territory` in `summary.json`). Our hypothesis, not yet tested, is that county differences mostly reflect
which EMCs and municipals share a county with it. Chatham has no baseline. The 2024 EIA-861
territory lists only Canoochee EMC for Chatham, and Canoochee files no SAIDI. Georgia Power's 2024
territory list omits Chatham, Union, Towns and Fannin.

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
| LOW | 50 | 17,545 | 9 | 13 |
| MEDIUM | 55 | 17,703 | 18 | 0 |
| HIGH | 21 | 12,369 | 13 | 0 |
| UNKNOWN | 33 | 44,950 | – | – |

Tier status: 74 `derived`, 39 `low_data`, 13 `suspect` (worst share capped from above 1; all LOW either
way), 33 `unrecorded` (UNKNOWN).

**44,950 of the 92,567 power-dependent residents (snapshot) live in UNKNOWN counties.**

**Sensitivity.** Of 126 tiered counties, 64 keep the same tier under all three rules.
- Terciles change 31 counties: 9 LOW→MEDIUM, 21 MEDIUM→HIGH, 1 MEDIUM→LOW.
- The median rule changes 43: 33 LOW→MEDIUM, 1 LOW→HIGH, 9 MEDIUM→HIGH. Most LOW counties are LOW because
  of one storm (Helene), not repeatedly.
- HIGH is the same under all three rules (21 of 21), but 13 of the 21 rest on a single hit storm.

**EIA corroboration (weak).** The median storm multiplier rises with the EAGLE-I tier: HIGH 3.04,
MEDIUM 3.57, LOW 3.68 (UNKNOWN 3.01). This agrees in direction and comes from an independent source, but
it is utility-wide.

**Baseline tiers.** LOW 52 counties (17,516 power-dependent), MEDIUM 53 (15,761), HIGH 53 (57,341),
UNKNOWN 1 (Chatham, 1,949).

**Baseline vs storm tier.** Of 125 counties with both, 54 get the same tier. Storm-LOW counties have
baseline LOW 25, MEDIUM 20, HIGH 4 (and Chatham UNKNOWN). Storm-HIGH counties have baseline HIGH 10,
MEDIUM 9, LOW 2. Storm-MEDIUM counties have baseline LOW 22, MEDIUM 19, HIGH 14. The baseline leans the
same way at the extremes but disagrees often, so treat it as a label, not a substitute. The 33
storm-UNKNOWN counties split baseline HIGH 25, MEDIUM 5, LOW 3. Fulton, Cobb, Gwinnett, Cherokee and Henry
are all baseline HIGH.

**LOW counties with the most power-dependent residents:**

| County | FIPS | Power-dependent | Hit storms | Worst peak share | Worst h to 90% restored (storm) | Worst h ≥10% out | Stable |
|---|---|---|---|---|---|---|---|
| Chatham | 13051 | 1,949 | Idalia, Helene | 0.73 | 135.0 (Helene) | 136.25 | no |
| Richmond | 13245 | 1,647 | Michael, Helene | 0.95 | 162.25 (Helene) | 248.0 | yes |
| Lowndes | 13185 | 1,160 | Idalia, Debby, Helene | 0.82 | 259.5 (Helene) | 257.25 | yes |
| Columbia | 13073 | 1,094 | Helene | 1.00 (suspect) | 143.0 (Helene) | 258.25 | yes |
| Glynn | 13127 | 907 | Idalia, Helene | 0.88 | 83.75 (Helene) | 92.25 | no |
| Coffee | 13069 | 720 | Michael, Idalia, Debby, Helene | 0.67 | 437.5 (Helene) | 335.0 | no |
| Tift | 13277 | 608 | Michael, Idalia, Debby, Helene | 1.00 (suspect) | 230.25 (Helene) | 248.75 | no |
| Ware | 13299 | 598 | Michael, Idalia, Helene | 0.90 | 260.5 (Helene) | 281.25 | no |
| Bulloch | 13031 | 550 | Michael, Idalia, Helene | 0.87 | 170.0 (Helene) | 183.25 | no |
| Colquitt | 13071 | 506 | Michael, Idalia, Debby, Helene, Milton | 0.82 | 122.75 (Helene) | 127.5 | no |

**UNKNOWN is large.** The 33 untiered counties hold 44,950 of 92,567 power-dependent residents. They include metro Atlanta: Fulton 5,804, Cobb 4,652, Gwinnett 4,492,
Cherokee 2,481, Henry 1,856. No 2018+ storm took 10% of their customers out; their worst recorded share
is at most 0.093 (median 0.058). That shows low *exposure* so far, not a reliable grid. 14 of them were
hit in Irma 2017, which is excluded as pre-2018.

**OE-417 cross-check.** OE-417 has a single Georgia filing per storm, each 34k–57k customers. EAGLE-I's
sum of county peaks is far larger (Irma 1,553,159, Michael 429,978, Matthew 322,240). The OE-417 filings
cover one utility's report, not the state, and there are no 2024 files, so OE-417 is not used in the tiers.

## Caveats

- **The tier measures exposure plus grid.** A county that sat in Helene's path is LOW even if its
  utility restored fast relative to the damage. LOW mostly reflects Helene, the worst storm in the record.
- **Restore times bias short.** EAGLE-I reads a single utility's feed gaps as zero outages.
- **Shares are approximate.** The denominator is EAGLE-I's 2024 attributed customers; 13 Helene counties
  exceed 1 before capping.
- **Restore is relative to the county's own peak.** It is the time until outages fall to 10% of peak,
  not to 10% of customers.
- **Small numbers.** 40 of 126 tiered counties rest on one hit storm (39 `low_data`; Columbia is
  `suspect`, which takes precedence).
- **EIA weights are approximate.** They assume a utility's customers spread evenly across its counties.
  66 of 97 serving utilities file no SAIDI. `baseline_tier` is utility-wide context with no storm test.
- **Inputs can change.** The inputs are external files. `summary.json` records their SHA-256, so a refresh
  shows up as a hash change.
- **Planning only.** Historical outage patterns, not a forecast and not live status.

## Attribution

- Brelsford et al., EAGLE-I Recorded Electricity Outages, ORNL / DOE CESER, Scientific Data 2024,
  doi:10.6084/m9.figshare.24237376.v4, CC BY 4.0. Changes: filtered to Georgia, aggregated to storm
  windows and county summaries.
- U.S. Energy Information Administration, Form EIA-861 (reliability and service territory), U.S. Government work.
- U.S. Department of Energy, Form OE-417 Electric Emergency Incident and Disturbance Reports, U.S. Government work.
- HHS emPOWER Program (ASPR/CMS), via the team's Georgia `power_dependent_counties` snapshot.
