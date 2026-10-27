// Mirrors specs/001-georgia-shelter-map/data-model.md and contracts/map-data.schema.json.
import type { Feature, LineString, MultiPolygon, Point, Polygon } from "geojson";

/** Never a boolean: a blank record is "not recorded", not "no" (Constitution I). */
export type Flag = "YES" | "NO" | "UNRECORDED";

export interface FlagCounts {
  yes: number;
  no: number;
  unrecorded: number;
}

export type ValueKind = "registry" | "survey" | "live" | "simulation";

export interface SourcedValue {
  value: number | null;
  /** Dataset and source table, e.g. "FEMA NSS registry · shelters" (Constitution III). */
  source: string;
  kind: ValueKind;
  coverage?: string;
}

export type QualityFlag = "suspect_capacity" | "location_disagrees";

export interface Shelter {
  shelter_id: string;
  name: string;
  address?: string;
  county_fips: string | null;
  county_name: string;
  lat: number;
  lon: number;
  evacuation_capacity: number | null;
  post_impact_capacity?: number | null;
  usage: string | null;
  wheelchair_accessible: Flag;
  generator_onsite: Flag;
  is_medical: Flag;
  in_surge_slosh_area: Flag;
  quality_flags: QualityFlag[];
}

export type FlagKey = "wheelchair_accessible" | "generator_onsite" | "is_medical" | "in_surge_slosh_area";

export interface ExcludedShelter {
  shelter_id: string;
  name: string;
}

export interface County {
  county_fips: string;
  name: string;
  shelter_count: number;
  capacity_total: SourcedValue;
  capacity_total_incl_suspect: SourcedValue;
  capacity_excluded: ExcludedShelter[];
  wheelchair: FlagCounts;
  generator: FlagCounts;
  medical: FlagCounts;
  in_surge: FlagCounts;
  households_no_vehicle: SourcedValue;
  share_65_plus: SourcedValue;
  share_disability: SourcedValue;
}

export interface MapData {
  schema: "map-data/v1";
  state: "GA";
  generated_at: string;
  shelters: Shelter[];
  counties: County[];
  notes: string[];
}

export type Category = 1 | 2 | 3 | 4 | 5;

export interface ReceivingEntry {
  shelter_id: string;
  rank: number;
  distance_km: SourcedValue;
  nearest_affected_county: string;
  reason: string;
}

export interface HurricaneScenario {
  track: LineString | Point;
  category: Category;
  half_width_km: number;
  band: Feature<Polygon | MultiPolygon>;
  cutoff_km: number;
  affected_county_fips: string[];
  affected_shelter_ids: string[];
  receiving: ReceivingEntry[];
}

export interface GroundingSource {
  title: string;
  uri: string;
  placeId?: string;
}

export interface AnswerSegment {
  text: string;
  kind: "live" | "registry";
  sources?: GroundingSource[];
}

export type ChatStatus = "pending" | "streaming" | "done" | "failed";

export interface ChatContext {
  county_fips: string | null;
  shelter_id: string | null;
  scenario: ScenarioContext | null;
}

export interface ScenarioContext {
  track: LineString | Point;
  category: Category;
  cutoff_km: number;
  affected_county_fips: string[];
  affected_shelter_ids: string[];
  receiving_top: string[];
}

export interface ChatExchange {
  id: string;
  question: string;
  context: ChatContext;
  status: ChatStatus;
  text: string;
  groundingMetadata?: GroundingMetadata;
  error?: string;
  referenced_shelter_ids: string[];
  referenced_county_fips: string[];
}

/** The subset of ADK/Gemini grounding metadata the UI reads (contracts §3). */
export interface GroundingMetadata {
  groundingChunks?: { maps?: { uri?: string; title?: string; placeId?: string } }[];
  groundingSupports?: {
    segment?: { startIndex?: number | null; endIndex?: number; text?: string };
    groundingChunkIndices?: number[];
  }[];
}
