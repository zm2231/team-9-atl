#!/usr/bin/env bash
# One-time, idempotent project setup: Artifact Registry repo, runtime and deployer service accounts,
# and Workload Identity Federation so GitHub Actions on main can deploy without a key.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format 'value(projectNumber)')"
POOL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}"

gcloud services enable --project "${PROJECT_ID}" \
  run.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com \
  bigquery.googleapis.com places.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  secretmanager.googleapis.com routes.googleapis.com cloudtrace.googleapis.com

gcloud artifacts repositories describe "${AR_REPO}" --project "${PROJECT_ID}" --location "${REGION}" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "${AR_REPO}" --project "${PROJECT_ID}" --location "${REGION}" \
    --repository-format docker --description "Team 9 container images"

for sa in "${RUNTIME_SA}" "${DEPLOY_SA}"; do
  gcloud iam service-accounts describe "${sa}" --project "${PROJECT_ID}" >/dev/null 2>&1 ||
    gcloud iam service-accounts create "${sa%%@*}" --project "${PROJECT_ID}"
done

for role in roles/bigquery.dataViewer roles/bigquery.jobUser roles/aiplatform.user roles/mcp.toolUser roles/serviceusage.serviceUsageConsumer roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "serviceAccount:${RUNTIME_SA}" \
    --role "${role}" --condition None --quiet >/dev/null
done

gcloud secrets add-iam-policy-binding routes-api-key --project "${PROJECT_ID}" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor --quiet >/dev/null
gcloud secrets describe maps-places-api-key --project "${PROJECT_ID}" >/dev/null 2>&1 ||
  gcloud secrets create maps-places-api-key --project "${PROJECT_ID}" --replication-policy automatic
gcloud secrets add-iam-policy-binding maps-places-api-key --project "${PROJECT_ID}" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member "serviceAccount:${DEPLOY_SA}" \
  --role roles/run.developer --condition None --quiet >/dev/null
gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" --project "${PROJECT_ID}" --location "${REGION}" \
  --member "serviceAccount:${DEPLOY_SA}" --role roles/artifactregistry.writer --quiet >/dev/null
gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA}" --project "${PROJECT_ID}" \
  --member "serviceAccount:${DEPLOY_SA}" --role roles/iam.serviceAccountUser --quiet >/dev/null

gcloud iam workload-identity-pools describe "${WIF_POOL}" --project "${PROJECT_ID}" --location global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create "${WIF_POOL}" --project "${PROJECT_ID}" --location global \
    --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER}" --project "${PROJECT_ID}" \
  --location global --workload-identity-pool "${WIF_POOL}" >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" --project "${PROJECT_ID}" \
    --location global --workload-identity-pool "${WIF_POOL}" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "assertion.repository == '${GITHUB_REPO}' && assertion.ref == 'refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding "${DEPLOY_SA}" --project "${PROJECT_ID}" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO}" --quiet >/dev/null

echo "WIF provider: ${POOL_ID}/providers/${WIF_PROVIDER}"
echo "Deploy service account: ${DEPLOY_SA}"

if gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1; then
  deploy/access.sh team
else
  echo "Run deploy/deploy.sh once, then deploy/access.sh team to put the service behind IAP."
fi
