#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

: "${AWS_REGION:=us-east-1}"
: "${ARTIFACT_BUCKET:=ddemo-artifacts-676206911400-us-east-1}"
: "${ARTIFACT_KEY:=releases/current.zip}"

terraform init -input=false
terraform destroy -auto-approve \
  -var="region=${AWS_REGION}" \
  -var="artifact_bucket=${ARTIFACT_BUCKET}" \
  -var="artifact_key=${ARTIFACT_KEY}"

#   USE: AWS_REGION=us-east-1 ./infra/wipe.sh