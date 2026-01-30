#!/bin/bash
# Verify V1 & V2 Fixes

echo "--- V1: Routing & Endpoints ---"
echo "Testing /v1/health..."
curl -s http://localhost:8000/v1/health | head -n 5
echo -e "\n\nTesting /v1/version..."
curl -s http://localhost:8000/v1/version
echo -e "\n"

echo "--- V2: Preview ---"
# List one document ID
echo "Fetching a document ID..."
DOC_ID=$(curl -s "http://localhost:8000/v1/documents?limit=1" | grep -oP '"id":"\K[^"]+')
echo "Document ID: $DOC_ID"

if [ -z "$DOC_ID" ]; then
    echo "No documents found. Skipping preview test (or upload one first)."
else
    echo "Testing Preview for $DOC_ID..."
    # 404/503 is expected if file missing in MinIO, but MUST be JSON not HTML
    curl -sI "http://localhost:8000/v1/documents/${DOC_ID}/preview" | head -n 5
    curl -s "http://localhost:8000/v1/documents/${DOC_ID}/preview" | head -n 5
fi
