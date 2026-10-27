#!/usr/bin/env bash
# Choose who can open the service.
# Usage: deploy/access.sh team     IAP sign-in for the accounts in deploy/iap_members.txt
#        deploy/access.sh public   no sign-in; a shared password (secret access-password) instead
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format 'value(projectNumber)')"
IAP_AGENT="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
RUN=(--project "${PROJECT_ID}" --region "${REGION}" --quiet)

case "${1:-}" in
  team)
    gcloud beta run services update "${SERVICE}" "${RUN[@]}" --iap >/dev/null
    gcloud run services add-iam-policy-binding "${SERVICE}" "${RUN[@]}" \
      --member "${IAP_AGENT}" --role roles/run.invoker >/dev/null
    gcloud run services remove-iam-policy-binding "${SERVICE}" "${RUN[@]}" \
      --member allUsers --role roles/run.invoker >/dev/null 2>&1 || true
    while read -r member; do
      [[ -z "${member}" ]] && continue
      gcloud beta iap web add-iam-policy-binding --resource-type cloud-run --service "${SERVICE}" \
        --region "${REGION}" --project "${PROJECT_ID}" --member "${member}" \
        --role roles/iap.httpsResourceAccessor --condition None --quiet >/dev/null
    done < deploy/iap_members.txt
    gcloud run services update "${SERVICE}" "${RUN[@]}" --remove-secrets ACCESS_PASSWORD >/dev/null
    echo "IAP on ${SERVICE} for $(grep -c . deploy/iap_members.txt) accounts"
    ;;
  public)
    if ! gcloud secrets describe access-password --project "${PROJECT_ID}" >/dev/null 2>&1; then
      openssl rand -base64 12 | tr -d '/+=\n' |
        gcloud secrets create access-password --project "${PROJECT_ID}" --data-file - >/dev/null
    fi
    gcloud secrets add-iam-policy-binding access-password --project "${PROJECT_ID}" \
      --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor \
      --condition None --quiet >/dev/null
    gcloud run services update "${SERVICE}" "${RUN[@]}" \
      --update-secrets ACCESS_PASSWORD=access-password:latest >/dev/null
    gcloud run services add-iam-policy-binding "${SERVICE}" "${RUN[@]}" \
      --member allUsers --role roles/run.invoker >/dev/null
    gcloud beta run services update "${SERVICE}" "${RUN[@]}" --no-iap >/dev/null
    echo "${SERVICE} is public behind the shared password. Read it with:"
    echo "  gcloud secrets versions access latest --secret access-password --project ${PROJECT_ID}"
    ;;
  *)
    echo "usage: deploy/access.sh team|public" >&2
    exit 2
    ;;
esac
