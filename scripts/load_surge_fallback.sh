#!/usr/bin/env bash
# Loads the NOAA surge fallback into BigQuery as <dataset>.shelter_surge_noaa_clean.
#
# The shelters table keeps FEMA's value untouched. The agent's SQL tools read this table only where
# the registry surge flag is blank (see _shelters_with_surge_fallback in evacuation_tools.py).
# Rebuild the CSV first with scripts/derive_shelter_surge.py. Safe to re-run: --replace.
#
#   bash scripts/load_surge_fallback.sh [PROJECT_ID] [DATASET]
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-edc952746633}}"
DATASET="${2:-${EVAC_DATASET:-evac_prod}}"
CSV="$(cd "$(dirname "$0")/.." && pwd)/agent/readiness_agent/data/shelter_surge_slosh.csv"

[ -f "${CSV}" ] || { echo "Missing ${CSV}; run scripts/derive_shelter_surge.py first." >&2; exit 1; }

# in_surge_fallback: TRUE flooded in some category, FALSE dry in all five, NULL levee area.
bq --project_id="${PROJECT_ID}" load \
  --source_format=CSV --skip_leading_rows=1 --replace \
  "${DATASET}.shelter_surge_noaa_clean" "${CSV}" \
  shelter_id:STRING,in_surge_fallback:BOOLEAN,status:STRING,first_category:INTEGER,cat1_class:INTEGER,cat2_class:INTEGER,cat3_class:INTEGER,cat4_class:INTEGER,cat5_class:INTEGER,searched:STRING

bq --project_id="${PROJECT_ID}" query --use_legacy_sql=false --format=pretty \
  "SELECT status, COUNT(*) AS shelters FROM \`${PROJECT_ID}.${DATASET}.shelter_surge_noaa_clean\` GROUP BY status ORDER BY status"
