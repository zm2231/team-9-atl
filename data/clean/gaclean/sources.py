import os
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()
HACK = HOME / "work" / "google-hackathon"


def _env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, default))


@dataclass(frozen=True)
class Sources:
    snapshot: Path
    empower_live_county: Path
    empower_live_zip: Path
    cms: Path
    dialysis_geocoded: Path
    overture_places: Path
    gema: Path
    gamap2care: Path
    ncei_storm_events: Path
    nss_activation: Path
    evac_orders: Path
    oe417: Path
    nhc_lead_times: Path

    @classmethod
    def from_env(cls) -> "Sources":
        extdata = _env("EXTDATA", HOME / "work" / "extdata")
        return cls(
            snapshot=_env("C4DATA_GA", HOME / "work" / "c4data" / "GA"),
            empower_live_county=extdata / "emPOWER" / "empower_ga_county.csv",
            empower_live_zip=extdata / "emPOWER" / "empower_ga_zip.csv",
            cms=_env("CMS_DIR", HACK / "prework" / "data" / "external" / "cms"),
            dialysis_geocoded=_env("DIALYSIS_GEOCODED", HACK / "c4-capabilities" / "out" / "dialysis_centers_geocoded.csv"),
            overture_places=_env("OVERTURE_PLACES", HACK / "prework" / "data" / "external" / "overture"
                                 / "places_ga_care_transport.parquet"),
            gema=extdata / "gema",
            gamap2care=extdata / "gamap2care" / "gamap2care_alc_pch_facility_fields.parquet",
            ncei_storm_events=extdata / "ncei_storm_events" / "ga_fl_tropical.parquet",
            nss_activation=extdata / "fema_nss" / "nss_ga_fl_last_activation.parquet",
            evac_orders=extdata / "ga_evac_orders" / "orders.csv",
            oe417=extdata / "oe417" / "oe417_ga_fl_weather_events.csv",
            nhc_lead_times=extdata / "nhc_advisories" / "storm_lead_times.parquet",
        )

    def check(self) -> None:
        paths = [self.snapshot / t / "data.parquet" for t in
                 ("shelters", "vulnerability_tracts", "hazard_tracts", "care_facilities", "power_dependent_counties")]
        paths += [self.empower_live_county, self.empower_live_zip, self.cms / "nursing_homes_ga.parquet",
                  self.cms / "dialysis_facilities_ga.parquet", self.dialysis_geocoded, self.overture_places,
                  self.gema / "evacuation_zones.geojson", self.gema / "contraflow_intersections.geojson",
                  self.gema / "shelters_v2_schema.json", self.gamap2care, self.ncei_storm_events,
                  self.nss_activation, self.evac_orders, self.oe417, self.nhc_lead_times]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            raise FileNotFoundError("missing inputs (see data/clean/SOURCES.md):\n  " + "\n  ".join(missing))
