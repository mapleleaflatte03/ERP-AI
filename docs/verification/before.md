# Baseline: ERP-AI Pipeline (Pre-Fix)

## Environment Metrics
- **Git SHA**: `75c4a1c7a681dd9a9b74017e7ad1d25f92dbc38e`
- **Docker Status**: All containers Up (healthy).
- **API Health**: Degraded (Database/Storage/VectorDB connection issues from host-run process).

## Pipeline Checklist (Before)

### (a) Tab "Hóa đơn" Filtering
**Command**: `curl -s "http://localhost:8000/v1/documents?type=invoice"`
**Observation**: Returns `{"total": 10, "documents": [...]}`. Total count works, but the frontend reported consistency issues.

### (b) XLSX Preview
**Command**: `curl -s "http://localhost:8000/v1/files/erpx-documents/test.xlsx?preview=true"`
**Observation**: `{"detail":"Missing authorization header"}`. Authenticated access is required; need to verify if content-type and conversion work correctly under auth.

### (c) Delete Functionality
**Command**: `curl -X DELETE "http://localhost:8000/v1/documents/test-id?confirm=true"`
**Observation**: Returns error or status 401/404. Deletion logic is often incomplete across related tables.

### (d) Reports (Dữ liệu thật/Biểu đồ)
**Command**: `curl -s "http://localhost:8000/v1/reports/timeseries?start_date=2025-01-01&end_date=2025-12-31"`
**Observation**: Returns fallback data `{"labels": ["2026-01"], "datasets": [{"label": "Doanh thu", "data": [0]}]}`. No real data integration yet.

### (e) Evidence Timeline
**Command**: `curl -s "http://localhost:8000/v1/evidence/timeline"`
**Observation**: Returns `[]`. No timeline events recorded yet.
