#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://app.welliam.codes}"

paths=(
  "/"
  "/proposals"
  "/approvals"
  "/copilot"
  "/analyze"
  "/evidence"
  "/admin/diagnostics"
)

echo "Smoke check: ${BASE_URL}"

for path in "${paths[@]}"; do
  echo "HEAD ${BASE_URL}${path}"
  curl -s -I "${BASE_URL}${path}" | head -n 1
  echo ""
done

echo "GET ${BASE_URL}/v1/health"
curl -s "${BASE_URL}/v1/health" | head -c 200 || true

echo ""
