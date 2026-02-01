#!/usr/bin/env bash
set -e;

IMAGE_TAG="gcr.io/whodis-fyi/whodis"

gcloud builds submit --tag ${IMAGE_TAG}
gcloud run deploy --image ${IMAGE_TAG} --platform managed whodis