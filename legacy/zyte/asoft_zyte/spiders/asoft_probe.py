"""
ASOFT Probe Spider - Safe Public Index Scanner
===============================================
Purpose: Lightly scan public index.html to discover:
- Internal links (<a href>)
- Script assets (<script src>)
- API endpoint hints in HTML/JS (/api/, /swagger, /v1/, etc.)

SAFETY GUARANTEES:
- NO authentication, NO login
- NO brute-force, NO port scanning
- ROBOTSTXT_OBEY = True
- DOWNLOAD_DELAY = 2s (minimum)
- CONCURRENT_REQUESTS = 1
- CLOSESPIDER_PAGECOUNT = 15 (max)
- Only GET requests
- Only same-host resources
"""

import re
from urllib.parse import urljoin, urlparse

import scrapy


class AsoftProbeSpider(scrapy.Spider):
    """
    Safe probe spider for discovering API hints from public index page.
    Target: http://202.78.231.242:8292/index.html (default)
    """

    name = "asoft_probe"

    # ========================================
    # SAFETY SETTINGS - DO NOT WEAKEN
    # ========================================
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,
        "CLOSESPIDER_PAGECOUNT": 15,
        "CLOSESPIDER_ITEMCOUNT": 500,
        "DOWNLOAD_TIMEOUT": 10,
        "LOG_LEVEL": "INFO",
        "RETRY_TIMES": 1,
        "DEPTH_LIMIT": 1,
        # Export JSONL for easy parsing
        "FEEDS": {
            "output/asoft_probe_%(time)s.jsonl": {
                "format": "jsonlines",
                "encoding": "utf-8",
            },
        },
    }

    # ========================================
    # API HINT PATTERNS
    # ========================================
    API_PATTERNS = [
        re.compile(r'["\']([^"\']*?/api/[^"\'\\s]{1,100})["\']', re.IGNORECASE),
        re.compile(r'["\']([^"\']*?/swagger[^"\'\\s]{0,100})["\']', re.IGNORECASE),
        re.compile(r'["\']([^"\']*?/api/v\d+[^"\'\\s]{0,100})["\']', re.IGNORECASE),
        re.compile(r'["\']([^"\']*?/v\d+/[^"\'\\s]{1,100})["\']', re.IGNORECASE),
        re.compile(r'["\']([^"\']*?graphql[^"\'\\s]{0,50})["\']', re.IGNORECASE),
        re.compile(r'["\']([^"\']*?/rest/[^"\'\\s]{1,100})["\']', re.IGNORECASE),
        # Catch endpoint patterns without quotes
        re.compile(r"(/api/v?\d*/[a-zA-Z0-9_/-]{1,80})", re.IGNORECASE),
    ]

    def __init__(self, base_url=None, max_js=10, *args, **kwargs):
        """
        Args:
            base_url: Target URL (default: http://202.78.231.242:8292/index.html)
            max_js: Max number of JS files to fetch (default: 10)
        """
        super().__init__(*args, **kwargs)
        self.base_url = base_url or "http://202.78.231.242:8292/index.html"
        self.max_js = int(max_js)
        self.js_fetched = 0

        # Parse host for same-origin check
        parsed = urlparse(self.base_url)
        self.allowed_host = parsed.netloc
        self.allowed_domains = [parsed.hostname] if parsed.hostname else []

        self.logger.info(f"[ASOFT_PROBE] Target: {self.base_url}")
        self.logger.info(f"[ASOFT_PROBE] Host: {self.allowed_host}")
        self.logger.info(f"[ASOFT_PROBE] Max JS files: {self.max_js}")

    def start_requests(self):
        """Start with single request to base_url"""
        self.logger.info(f"[ASOFT_PROBE] Starting probe of {self.base_url}")
        yield scrapy.Request(
            self.base_url,
            callback=self.parse_index,
            errback=self.handle_error,
            dont_filter=True,
        )

    def parse_index(self, response):
        """
        Parse the main index.html page.
        Extract: links, scripts, API hints from HTML.
        """
        self.logger.info(f"[ASOFT_PROBE] Parsing index: {response.url} (status: {response.status})")

        # 1) Yield page meta item
        yield {
            "kind": "page",
            "value": response.url,
            "status": response.status,
            "content_type": response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore"),
            "source_url": response.url,
            "base_url": self.base_url,
        }

        html_text = response.text or ""

        # 2) Extract API hints from HTML/inline JS
        for hint in self._extract_api_hints(html_text):
            yield {
                "kind": "api_hint",
                "value": hint,
                "source_url": response.url,
                "base_url": self.base_url,
            }

        # 3) Extract internal links (only log, don't follow)
        hrefs = response.css("a::attr(href)").getall()
        seen_links = set()
        for href in hrefs:
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            abs_url = urljoin(response.url, href)
            if self._same_host(abs_url) and abs_url not in seen_links:
                seen_links.add(abs_url)
                yield {
                    "kind": "link",
                    "value": abs_url,
                    "source_url": response.url,
                    "base_url": self.base_url,
                }

        # 4) Extract external script sources and fetch (limited)
        script_srcs = response.css("script::attr(src)").getall()
        js_urls = []

        for src in script_srcs:
            if not src:
                continue
            abs_url = urljoin(response.url, src)
            if self._same_host(abs_url) and abs_url.endswith((".js", ".mjs")):
                js_urls.append(abs_url)

        # Limit JS files
        js_urls = js_urls[: self.max_js]
        self.logger.info(f"[ASOFT_PROBE] Found {len(js_urls)} JS files to probe")

        for js_url in js_urls:
            yield {
                "kind": "script",
                "value": js_url,
                "source_url": response.url,
                "base_url": self.base_url,
            }

            if self.js_fetched < self.max_js:
                self.js_fetched += 1
                yield scrapy.Request(
                    js_url,
                    callback=self.parse_js,
                    errback=self.handle_error,
                    dont_filter=True,
                )

    def parse_js(self, response):
        """
        Parse JavaScript file content for API hints.
        Only extracts patterns, does NOT execute JS.
        """
        self.logger.info(f"[ASOFT_PROBE] Parsing JS: {response.url}")

        js_text = response.text or ""

        # Only look for API hints
        hints = self._extract_api_hints(js_text)
        self.logger.info(f"[ASOFT_PROBE] Found {len(hints)} API hints in {response.url}")

        for hint in hints:
            yield {
                "kind": "api_hint",
                "value": hint,
                "source_url": response.url,
                "base_url": self.base_url,
            }

    def _extract_api_hints(self, text: str) -> list:
        """
        Extract API endpoint hints from text using regex patterns.
        Returns deduplicated, sorted list of hints.
        """
        found = set()

        for pattern in self.API_PATTERNS:
            for match in pattern.findall(text):
                # Handle both string and tuple (from groups)
                hint = match if isinstance(match, str) else match[0]
                hint = hint.strip()

                # Filter: reasonable length, no obvious garbage
                if 3 <= len(hint) <= 200:
                    # Skip common false positives
                    if any(
                        skip in hint.lower()
                        for skip in [
                            "node_modules",
                            "webpack",
                            ".map",
                            "sourcemap",
                            "localhost",
                            "127.0.0.1",
                            "example.com",
                        ]
                    ):
                        continue
                    found.add(hint)

        return sorted(found)

    def _same_host(self, url: str) -> bool:
        """Check if URL is same host as target"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.allowed_host
        except Exception:
            return False

    def handle_error(self, failure):
        """Log errors gracefully"""
        self.logger.warning(f"[ASOFT_PROBE] Request failed: {failure.request.url} - {failure.value}")
