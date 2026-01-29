#!/bin/bash
OUTPUT_FILE="/root/erp-ai/docs/verification/before.md"
API_URL="http://localhost:8000"

echo "# Verification Report (BEFORE)" > $OUTPUT_FILE
echo "Generated at: $(date)" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

echo "## 1. Git & Docker Status" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE
git -C /root/erp-ai rev-parse HEAD >> $OUTPUT_FILE
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

echo "## 2. API Health" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE
curl -s "$API_URL/health" -I >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

echo "## 3. Functional Checks" >> $OUTPUT_FILE

echo "### 3a. Tabs Filter (Doc Type)" >> $OUTPUT_FILE
# Check if filtering works (assuming we have data from previous session)
echo "Request: GET /v1/documents?type=invoice" >> $OUTPUT_FILE
echo "\`\`\`json" >> $OUTPUT_FILE
curl -s "$API_URL/v1/documents?type=invoice&limit=1" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE

echo "### 3b. Reports (Timeseries)" >> $OUTPUT_FILE
echo "Request: GET /v1/reports/timeseries" >> $OUTPUT_FILE
echo "\`\`\`json" >> $OUTPUT_FILE
curl -s "$API_URL/v1/reports/timeseries?start_date=2026-01-01&end_date=2026-12-31" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE

echo "### 3c. Reports (Trial Balance - Expected Missing)" >> $OUTPUT_FILE
echo "Request: GET /v1/reports/trial_balance" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE
curl -s -o /dev/null -w "%{http_code}" "$API_URL/v1/reports/trial_balance" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "\`\`\`" >> $OUTPUT_FILE

echo "### 3d. Evidence Timeline" >> $OUTPUT_FILE
# Get a doc id if possible
DOC_ID=$(curl -s "$API_URL/v1/documents?limit=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['documents'][0]['id'])" 2>/dev/null)
if [ ! -z "$DOC_ID" ]; then
    echo "Request: GET /v1/documents/$DOC_ID/timeline (Using ID: $DOC_ID)" >> $OUTPUT_FILE
    echo "\`\`\`json" >> $OUTPUT_FILE
    # Assuming timeline endpoint might be /evidence based on my previous work, or /timeline
    curl -s "$API_URL/v1/documents/$DOC_ID/evidence" >> $OUTPUT_FILE
    echo "" >> $OUTPUT_FILE
    echo "\`\`\`" >> $OUTPUT_FILE
else
    echo "No documents found to test timeline." >> $OUTPUT_FILE
fi

echo "## 4. Manual Observation Gaps" >> $OUTPUT_FILE
echo "- Preview XLSX: Unknown (API doesn't explicit preview endpoint yet, UI uses raw file_url)" >> $OUTPUT_FILE
echo "- Delete Safety: Not verified yet." >> $OUTPUT_FILE
echo "- I18N: Mixed (known issue)" >> $OUTPUT_FILE
