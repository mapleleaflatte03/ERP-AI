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

health_paths=(
  "/health"
)

echo "Smoke check: ${BASE_URL}"

for path in "${paths[@]}"; do
  echo "HEAD ${BASE_URL}${path}"
  curl -s -I "${BASE_URL}${path}" | head -n 1
  echo ""
done

health_ok=0
for health_path in "${health_paths[@]}"; do
  echo "GET ${BASE_URL}${health_path}"
  response=$(curl -s -w "\n%{http_code}" "${BASE_URL}${health_path}" || true)
  body=$(echo "$response" | sed '$d')
  code=$(echo "$response" | tail -n 1)
  echo "$body" | head -c 200
  echo ""
  if [[ "$code" == "200" ]]; then
    health_ok=1
    break
  fi
done

if [[ "$health_ok" -ne 1 ]]; then
  echo "Health check failed for all endpoints: ${health_paths[*]}" >&2
  exit 1
fi

echo ""
