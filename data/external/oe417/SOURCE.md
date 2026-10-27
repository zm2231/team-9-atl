# DOE OE-417 Electric Emergency Incident and Disturbance Reports: GA/FL weather events 2013-2023

- **Source URL(s):** DOE CESER annual summaries, originally https://www.oe.netl.doe.gov/OE417_annual_summary.aspx (files `download.aspx?type=OE417XLS&ID=<n>`). That host no longer resolves in DNS (checked 2026-10-27 with system resolver, 8.8.8.8 and 1.1.1.1), so the XLS files were fetched from Internet Archive captures of the original URLs: `https://web.archive.org/web/<timestamp>id_/https://www.oe.netl.doe.gov/download.aspx?type=OE417XLS&ID=<n>`. Latest capture per ID was used except ID 78 (2018), capture 20210419110709.
- **Fetched:** 2026-10-27
- **Publisher update date:** Per-file; captures dated 2021-04 to 2024-12. ID to year: 41=2013, 62=2014, 75=2015, 76=2016, 77=2017, 78=2018, 79=2019, 80=2020, 81=2021, 82=2022, 84=2023 (year verified from min/max event dates in each file).
- **License / terms:** US Government work (Department of Energy, Form OE-417 is a mandatory federal filing published by DOE). Not subject to copyright in the US (17 U.S.C. 105). No licence text could be retrieved from the live site because it is offline.
- **Terms URL:** https://www.law.cornell.edu/uscode/text/17/105 ; original page https://www.oe.netl.doe.gov/OE417_annual_summary.aspx (offline)
- **Attribution:** Source: U.S. Department of Energy, Form OE-417 Electric Emergency Incident and Disturbance Reports, annual summaries 2013-2023 (retrieved via Internet Archive), accessed 2026-10-27
- **Coverage:** 2013-2023 national annual files (11 years). Extract: 73 rows where Area Affected mentions Georgia or Florida and Event Type mentions weather/hurricane/tropical/storm/natural disaster.
- **Public repo + video safe?** Yes. Utility-level and state-level event rows only; the current captures contain no Respondent/contact names.

## Notes

- OE-417 is event-level and utility-reported, not county time series. "Number of Customers Affected" is per filing (one storm can have several filings from different utilities; do not sum across rows without care). Values may be "Unknown".
- Dates: 2013-2016 files store real dates; 2017+ store MM/DD/YYYY strings; both parsed into `date_event_began`.
- `storm_window` tags rows whose start date falls in a named-storm window (Hermine, Matthew, Irma, Michael, Dorian, Sally, Zeta, Elsa, Ian, Nicole, Idalia). No Idalia (Aug 2023) or Dorian rows matched in the 2023/2019 files as captured.
- 2024 and 2025 annual files were not available (live site offline, no Wayback capture found for IDs 85-87).
- Raw XLS kept in `raw/` (about 1.1 MB). Extract script: scratchpad `outages/oe417.py`.

## Files

### `oe417_ga_fl_weather_events.csv` (73 rows)

Columns: Date Event Began, Time Event Began, Date of Restoration, Time of Restoration, Area Affected, NERC Region, Event Type, Demand Loss (MW), Number of Customers Affected, source_file, Alert Criteria, date_event_began, state_ga, state_fl, storm_window

### `raw/oe417_id{41,62,75,76,77,78,79,80,81,82,84}.xls`

National annual summaries as published.
