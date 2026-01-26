"""
ERPX AI - Unified LLM Client
============================
DO Agent qwen3-32b ONLY - NO LOCAL LLM SUPPORT

This is the single entry point for all LLM calls in the system.
Local LLM code has been REMOVED per production requirements.

Environment Variables (REQUIRED):
    LLM_PROVIDER=do_agent (MUST be "do_agent")
    DO_AGENT_URL=<endpoint>
    DO_AGENT_API_KEY=<key>
    DO_AGENT_MODEL=qwen3-32b
    DO_AGENT_TIMEOUT=60
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Import JSON utilities for robust parsing
from core.json_utils import (
    extract_json_block,
    repair_json_light,
    safe_json_loads,
    try_parse_json_robust,
)

# Configure logging
logger = logging.getLogger("erpx.llm")


class LLMProviderError(Exception):
    """Raised when LLM provider is misconfigured"""

    pass


class LLMInferenceError(Exception):
    """Raised when LLM inference fails"""

    pass


class LLMTimeoutError(Exception):
    """Raised when LLM request times out"""

    pass


@dataclass
class LLMConfig:
    """LLM Configuration - DO Agent ONLY"""

    provider: str = "do_agent"
    url: str = ""
    api_key: str = ""
    model: str = "qwen3-32b"
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load config from environment variables"""
        provider = os.getenv("LLM_PROVIDER", "")

        # STRICT: Only do_agent is allowed
        if provider.lower() != "do_agent":
            raise LLMProviderError(
                f"INVALID LLM_PROVIDER='{provider}'. "
                "ONLY 'do_agent' is allowed in production. "
                "Set LLM_PROVIDER=do_agent"
            )

        url = os.getenv("DO_AGENT_URL", "")
        api_key = os.getenv("DO_AGENT_API_KEY", "") or os.getenv("DO_AGENT_KEY", "")
        model = os.getenv("DO_AGENT_MODEL", "qwen3-32b")
        timeout = int(os.getenv("DO_AGENT_TIMEOUT", "60"))

        if not url:
            raise LLMProviderError("DO_AGENT_URL is required but not set")
        if not api_key:
            raise LLMProviderError("DO_AGENT_API_KEY is required but not set")

        return cls(provider="do_agent", url=url.rstrip("/"), api_key=api_key, model=model, timeout=timeout)

    def mask_key(self) -> str:
        """Return masked API key for logging"""
        if not self.api_key:
            return "[NOT SET]"
        return f"...{self.api_key[-4:]}" if len(self.api_key) > 4 else "***"


@dataclass
class LLMRequest:
    """LLM Request"""

    prompt: str
    system: str = ""
    temperature: float = 0.3
    max_tokens: int = 2048
    json_schema: dict | None = None
    request_id: str = ""
    trace_id: str = ""

    def __post_init__(self):
        if not self.request_id:
            self.request_id = hashlib.md5(f"{time.time()}-{self.prompt[:50]}".encode()).hexdigest()[:12]


@dataclass
class LLMResponse:
    """LLM Response"""

    content: str
    model: str
    provider: str
    request_id: str
    trace_id: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "metadata": self.metadata,
        }


class LLMClient:
    """
    Unified LLM Client - DO Agent qwen3-32b ONLY

    Features:
    - Single provider: DigitalOcean Agent (qwen3-32b)
    - Automatic retry with exponential backoff
    - Request/response logging with trace_id
    - JSON schema enforcement
    - Circuit breaker (basic)
    - Async support (new)

    Usage:
        client = LLMClient()
        # Async
        response = await client.generate(
            prompt="Extract invoice fields...",
            system="You are an accounting expert",
            json_schema={"type": "object", ...}
        )
        # Sync (legacy)
        response = client.generate_sync(...)
    """

    def __init__(self, config: LLMConfig | None = None):
        """Initialize LLM Client"""
        self.config = config or LLMConfig.from_env()

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_open_until = 0

        logger.info("LLMClient initialized")
        logger.info(f"  Provider: {self.config.provider}")
        logger.info(f"  Model: {self.config.model}")
        logger.info(f"  URL: {self.config.url[:50]}...")
        logger.info(f"  API Key: {self.config.mask_key()}")
        logger.info(f"  Timeout: {self.config.timeout}s")

    def _check_circuit(self):
        """Check if circuit breaker is open"""
        if self._circuit_open:
            if time.time() >= self._circuit_open_until:
                logger.info("Circuit breaker: Half-open, allowing retry")
                self._circuit_open = False
            else:
                remaining = int(self._circuit_open_until - time.time())
                raise LLMInferenceError(f"Circuit breaker OPEN. Retry in {remaining}s. Too many consecutive failures.")

    def _record_success(self):
        """Record successful call"""
        self._consecutive_failures = 0
        self._circuit_open = False

    def _record_failure(self):
        """Record failed call, potentially trip circuit"""
        self._consecutive_failures += 1
        if self._consecutive_failures >= 5:
            self._circuit_open = True
            self._circuit_open_until = time.time() + 60  # 60s cooldown
            logger.error(f"Circuit breaker TRIPPED after {self._consecutive_failures} failures")

    def _prepare_request_body_and_headers(self, request: LLMRequest):
        """Prepare request body and headers (shared between sync and async)"""
        # Build messages
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        # Build request body
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Add JSON schema if provided
        if request.json_schema:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-Request-ID": request.request_id,
        }
        if request.trace_id:
            headers["X-Trace-ID"] = request.trace_id

        return body, headers

    def _process_response_data(self, data: dict, start_time: float, request: LLMRequest) -> LLMResponse:
        """Process response data (shared between sync and async)"""
        latency_ms = (time.time() - start_time) * 1000

        # Extract response content
        content = ""
        if "choices" in data and len(data["choices"]) > 0:
            message = data["choices"][0].get("message", {})
            content = message.get("content", "")
            # Qwen3 uses reasoning_content for thinking, fallback if content is empty
            if not content and "reasoning_content" in message:
                content = f"[Reasoning] {message.get('reasoning_content', '')}"

        # Token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        logger.info(
            f"[{request.request_id}] DO Agent response: "
            f"latency={latency_ms:.0f}ms tokens={input_tokens}+{output_tokens}"
        )

        return LLMResponse(
            content=content,
            model=self.config.model,
            provider="do_agent",
            request_id=request.request_id,
            trace_id=request.trace_id,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata={"raw_response": data, "timestamp": datetime.utcnow().isoformat()},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    def _call_do_agent_sync(self, request: LLMRequest) -> LLMResponse:
        """Call DO Agent API (Synchronous)"""
        start_time = time.time()
        body, headers = self._prepare_request_body_and_headers(request)

        logger.info(f"[{request.request_id}] DO Agent request (sync): model={self.config.model}")
        logger.debug(f"[{request.request_id}] Prompt: {request.prompt[:100]}...")

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                response = client.post(f"{self.config.url}/api/v1/chat/completions", json=body, headers=headers)
                response.raise_for_status()

            data = response.json()
            return self._process_response_data(data, start_time, request)

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[{request.request_id}] DO Agent TIMEOUT after {latency_ms:.0f}ms")
            raise LLMTimeoutError(f"DO Agent timeout after {latency_ms:.0f}ms") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request.request_id}] DO Agent HTTP error: "
                f"status={e.response.status_code} body={e.response.text[:200]}"
            )
            raise LLMInferenceError(f"DO Agent HTTP {e.response.status_code}: {e.response.text[:200]}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _call_do_agent(self, request: LLMRequest) -> LLMResponse:
        """Call DO Agent API (Async)"""
        start_time = time.time()
        body, headers = self._prepare_request_body_and_headers(request)

        logger.info(f"[{request.request_id}] DO Agent request (async): model={self.config.model}")
        logger.debug(f"[{request.request_id}] Prompt: {request.prompt[:100]}...")

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(f"{self.config.url}/api/v1/chat/completions", json=body, headers=headers)
                response.raise_for_status()

            data = response.json()
            return self._process_response_data(data, start_time, request)

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[{request.request_id}] DO Agent TIMEOUT after {latency_ms:.0f}ms")
            raise LLMTimeoutError(f"DO Agent timeout after {latency_ms:.0f}ms") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request.request_id}] DO Agent HTTP error: "
                f"status={e.response.status_code} body={e.response.text[:200]}"
            )
            raise LLMInferenceError(f"DO Agent HTTP {e.response.status_code}: {e.response.text[:200]}") from e

    def _prepare_request_object(self, prompt, system, json_schema, temperature, max_tokens, request_id, trace_id):
        self._check_circuit()
        return LLMRequest(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema,
            request_id=request_id or "",
            trace_id=trace_id or "",
        )

    def generate_sync(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_id: str = "",
        trace_id: str = "",
    ) -> LLMResponse:
        """Generate LLM response (Synchronous)"""
        request = self._prepare_request_object(prompt, system, json_schema, temperature, max_tokens, request_id, trace_id)
        try:
            response = self._call_do_agent_sync(request)
            self._record_success()
            return response
        except Exception:
            self._record_failure()
            raise

    async def generate(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_id: str = "",
        trace_id: str = "",
    ) -> LLMResponse:
        """Generate LLM response (Async)"""
        request = self._prepare_request_object(prompt, system, json_schema, temperature, max_tokens, request_id, trace_id)
        try:
            response = await self._call_do_agent(request)
            self._record_success()
            return response
        except Exception:
            self._record_failure()
            raise

    def generate_json_sync(
        self,
        prompt: str,
        system: str = "",
        schema: dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_id: str = "",
        trace_id: str = "",
        allow_self_fix: bool = True,
    ) -> dict[str, Any]:
        """Generate JSON (Synchronous)"""
        response = self.generate_sync(
            prompt=prompt,
            system=system,
            json_schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            request_id=request_id,
            trace_id=trace_id,
        )
        return self._process_json_response_sync(response, request_id, trace_id, allow_self_fix)

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        schema: dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_id: str = "",
        trace_id: str = "",
        allow_self_fix: bool = True,
    ) -> dict[str, Any]:
        """Generate JSON (Async)"""
        response = await self.generate(
            prompt=prompt,
            system=system,
            json_schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            request_id=request_id,
            trace_id=trace_id,
        )
        return await self._process_json_response_async(response, request_id, trace_id, allow_self_fix)

    def _process_json_response_sync(self, response: LLMResponse, request_id: str, trace_id: str, allow_self_fix: bool) -> dict[str, Any]:
        """Shared logic for parsing JSON response (Sync)"""
        content = response.content.strip()
        raw_preview = content[:200] if len(content) > 200 else content

        obj, err, stage = try_parse_json_robust(content)
        if obj is not None:
            if stage != "direct":
                logger.info(f"[{request_id}] JSON parsed via '{stage}'")
            return obj

        logger.warning(f"[{request_id}] JSON parse failed stages 1-3: {err}")

        if allow_self_fix:
            logger.info(f"[{request_id}] Attempting LLM self-fix (Sync)")
            try:
                fixed_content = self._llm_fix_json_sync(content, f"{request_id}-fix", trace_id)
                obj, err, stage = try_parse_json_robust(fixed_content)
                if obj is not None:
                    return obj
            except Exception as e:
                logger.warning(f"[{request_id}] Self-fix failed: {e}")

        raise ValueError(f"LLM response is not valid JSON. Error: {err}")

    async def _process_json_response_async(self, response: LLMResponse, request_id: str, trace_id: str, allow_self_fix: bool) -> dict[str, Any]:
        """Shared logic for parsing JSON response (Async)"""
        content = response.content.strip()
        raw_preview = content[:200] if len(content) > 200 else content

        obj, err, stage = try_parse_json_robust(content)
        if obj is not None:
            if stage != "direct":
                logger.info(f"[{request_id}] JSON parsed via '{stage}'")
            return obj

        logger.warning(f"[{request_id}] JSON parse failed stages 1-3: {err}")

        if allow_self_fix:
            logger.info(f"[{request_id}] Attempting LLM self-fix (Async)")
            try:
                fixed_content = await self._llm_fix_json(content, f"{request_id}-fix", trace_id)
                obj, err, stage = try_parse_json_robust(fixed_content)
                if obj is not None:
                    return obj
            except Exception as e:
                logger.warning(f"[{request_id}] Self-fix failed: {e}")

        raise ValueError(f"LLM response is not valid JSON. Error: {err}")

    def _llm_fix_json_sync(self, broken_json: str, request_id: str = "", trace_id: str = "") -> str:
        """Fix JSON using LLM (Sync)"""
        fix_prompt, fix_system = self._prepare_fix_prompt(broken_json)
        response = self.generate_sync(
            prompt=fix_prompt,
            system=fix_system,
            temperature=0,
            max_tokens=2048,
            request_id=request_id,
            trace_id=trace_id,
        )
        return response.content.strip()

    async def _llm_fix_json(self, broken_json: str, request_id: str = "", trace_id: str = "") -> str:
        """Fix JSON using LLM (Async)"""
        fix_prompt, fix_system = self._prepare_fix_prompt(broken_json)
        response = await self.generate(
            prompt=fix_prompt,
            system=fix_system,
            temperature=0,
            max_tokens=2048,
            request_id=request_id,
            trace_id=trace_id,
        )
        return response.content.strip()

    def _prepare_fix_prompt(self, broken_json: str):
        max_input = 2000
        if len(broken_json) > max_input:
            broken_json = broken_json[:max_input] + "..."

        fix_prompt = f"Convert the following into valid JSON. Output JSON ONLY. No commentary.\n\n```\n{broken_json}\n```\nValid JSON:"
        fix_system = "You are a JSON repair tool. Output only valid JSON."
        return fix_prompt, fix_system

    def health_check(self) -> dict[str, Any]:
        """Check LLM service health (Sync)"""
        try:
            start = time.time()
            response = self.generate_sync(prompt="Say 'OK' in one word.", max_tokens=10)
            latency = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "provider": "do_agent",
                "model": self.config.model,
                "latency_ms": latency,
                "response": response.content[:50],
            }
        except Exception as e:
            return {"status": "unhealthy", "provider": "do_agent", "model": self.config.model, "error": str(e)}


# Global client instance (lazy loaded)
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get global LLM client instance"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


# Convenience functions
def generate_sync(
    prompt: str,
    system: str = "",
    json_schema: dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    request_id: str = "",
    trace_id: str = "",
) -> LLMResponse:
    """Generate LLM response using global client (Sync)"""
    return get_llm_client().generate_sync(
        prompt=prompt,
        system=system,
        json_schema=json_schema,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=request_id,
        trace_id=trace_id,
    )

async def generate(
    prompt: str,
    system: str = "",
    json_schema: dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    request_id: str = "",
    trace_id: str = "",
) -> LLMResponse:
    """Generate LLM response using global client (Async)"""
    return await get_llm_client().generate(
        prompt=prompt,
        system=system,
        json_schema=json_schema,
        temperature=temperature,
        max_tokens=max_tokens,
        request_id=request_id,
        trace_id=trace_id,
    )

if __name__ == "__main__":
    # Test the client
    import sys

    print("=" * 60)
    print("ERPX AI LLM Client Test")
    print("=" * 60)

    try:
        client = LLMClient()
        print("\n✓ Client initialized successfully")

        print("\nRunning health check...")
        health = client.health_check()
        print(f"Health: {json.dumps(health, indent=2)}")

        if health["status"] == "healthy":
            print("\n✓ DO Agent qwen3-32b is working!")
        else:
            print("\n✗ DO Agent health check failed")
            sys.exit(1)

    except LLMProviderError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nRequired environment variables:")
        print("  export LLM_PROVIDER=do_agent")
        print("  export DO_AGENT_URL=https://your-agent-url")
        print("  export DO_AGENT_API_KEY=your-api-key")
        print("  export DO_AGENT_MODEL=qwen3-32b")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
