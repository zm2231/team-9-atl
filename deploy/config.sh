# shellcheck shell=bash disable=SC2034
PROJECT_ID=qwiklabs-gcp-04-edc952746633
REGION=us-east1
SERVICE=evac-readiness-agent
AR_REPO=team9
RUNTIME_SA=evac-agent-run@${PROJECT_ID}.iam.gserviceaccount.com
DEPLOY_SA=github-deployer@${PROJECT_ID}.iam.gserviceaccount.com
GITHUB_REPO=zm2231/team-9-atl
WIF_POOL=github
WIF_PROVIDER=team-9-atl
IMAGE_BASE=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}
SESSION_ENGINE="projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines/1590957041508155392"
