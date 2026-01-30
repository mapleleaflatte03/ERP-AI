# Routing Fix Verification (V1)

## Issue
Production `/v1/*` routes were falling through to the UI (index.html), causing JSON parsers to fail. Specifically `/v1/health` returned `text/html`.

## Fix Applied
1.  Modified `src/api/main.py` to alias `/health` to `/v1/health`.
2.  Added `/v1/version` endpoint explicitly in `src/api/main.py`.
3.  Ensure `ui/nginx.conf` has `location /v1/` proxying to backend (applied in previous pass).

## Verification (Local)

**Command:**
```bash
curl -s http://localhost:8000/v1/health | head -n 5
curl -s http://localhost:8000/v1/version
```

**Output:**
```json
{"status":"degraded","version":"1.0.0","timestamp":"...","services":{...}}
{"commit":"unknown","build_time":"...","status":"active"}
```

**Content-Type Check:**
```bash
$ curl -sI http://localhost:8000/v1/health | grep "content-type"
content-type: application/json
```

## Conclusion
The API now natively supports `/v1/health` and `/v1/version`, ensuring that even if Nginx proxies `/v1/` directly, the API responds correctly with JSON.
