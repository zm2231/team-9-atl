#!/usr/bin/env bash
# Build the agent image, push it to Artifact Registry and roll it out to Cloud Run.
# Usage: deploy/deploy.sh [tag]   (tag defaults to the current commit)
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

TAG="${1:-$(git rev-parse --short=12 HEAD)}"
IMAGE="${IMAGE_BASE}:${TAG}"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build --platform linux/amd64 -t "${IMAGE}" .
docker push "${IMAGE}"

gcloud run deploy "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --service-account "${RUNTIME_SA}" \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,EVAC_DATASET=evac_prod,MODEL_NAME=gemini-3-flash-preview,TRACE_TO_CLOUD=true" \
  --update-secrets "ROUTES_API_KEY=routes-api-key:latest,GOOGLE_MAPS_API_KEY=maps-places-api-key:latest" \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 1 \
  --quiet

gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format 'value(status.url)'
