"""
DigitalOcean Agent API Client for ERPX
Integrates Qwen3-32B via OpenAI-compatible endpoint.

Environment Variables:
- LLM_PROVIDER: "do_agent" to enable this client
- DO_AGENT_URL: Base URL (e.g., https://gdfyu2bkvuq4idxkb6x2xkpe.agents.do-ai.run)
- DO_AGENT_KEY: API key (never logged)
- DO_AGENT_MODEL: Model name (default: qwen3-32b)
- DO_AGENT_TIMEOUT: Request timeout in seconds (default: 60)
"""

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("DOAgentClient")

# ==============================================================================
# CONFIGURATION (from env, NEVER hardcode secrets)
# ==============================================================================


def get_do_agent_config() -> dict[str, Any]:
    """Load DO Agent configuration from environment variables."""
    return {
        "provider": os.getenv("LLM_PROVIDER", "local"),
        "url": os.getenv("DO_AGENT_URL", ""),
        "key": os.getenv("DO_AGENT_KEY", ""),
        "model": os.getenv("DO_AGENT_MODEL", "qwen3-32b"),
        "timeout": int(os.getenv("DO_AGENT_TIMEOUT", "60")),
    }


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask a secret, showing only last N characters."""
    if not secret or len(secret) <= visible_chars:
        return "****"
    masked_len = len(secret) - visible_chars
    return "*" * masked_len + secret[-visible_chars:]


# ==============================================================================
# PROMPT TEMPLATE (strict JSON output)
# ==============================================================================

SYSTEM_PROMPT = """You are ERPX Accounting Coding Engine (Vietnam VAS style).
Your ONLY output format is valid JSON. Never include markdown, backticks, or explanatory text outside JSON.
All responses must be parseable by json.loads() directly."""

USER_PROMPT_TEMPLATE = """YOU ARE WORKING IN A REAL PRODUCTION ERP SYSTEM (ERPX AI Accounting).
You are the "Accounting Coding Engine" for Vietnam VAS.
Your output will be executed by an ERP posting pipeline, so it MUST be correct, auditable, and JSON-only.

============================================================
INPUT JSON (REAL PRODUCTION DATA)
============================================================
{invoice_json}

============================================================
MISSION
============================================================
From the input invoice + OCR extraction + context (tenant, chart_of_accounts, vendor/customer),
create an accounting PROPOSAL (journal suggestion) exactly like a real accountant in ERP.

============================================================
HARD RULES (MUST FOLLOW)
============================================================
1) OUTPUT MUST BE VALID JSON ONLY.
   - No markdown, no comments, no extra text.
   - Must be parseable by json.loads(content).

2) NEVER INVENT NUMBERS.
   - Only use numeric values present in input OR derived strictly from rules below.
   - If you cannot derive safely -> needs_human_review=true.

3) ALWAYS include these fields at top-level:
   - invoice_id (string)
   - tenant_id (string)
   - trace_id (string)
   - needs_human_review (boolean)
   - confidence (0.0 .. 1.0)
   - risks (array of strings)
   - assumptions (array of strings)
   - evidence_fields_used (array of strings)  // global evidence paths used
   - explanation (string)  // short, factual
   - suggested_entries (array)
   - evidence (array)      // flat evidence list for audit/DB compatibility

4) FORMAT: suggested_entries[]
   Each entry MUST contain:
   {{
     "line_no": integer starting from 1,
     "debit_account": "string",
     "debit_account_name": "string or null",
     "credit_account": "string",
     "credit_account_name": "string or null",
     "amount": number,
     "currency": "VND" or from input,
     "description": "string",
     "evidence_fields": ["json.path.1", "json.path.2", ...]
   }}

5) EVIDENCE RULE (MANDATORY)
   - Each suggested entry MUST include evidence_fields (array of JSON paths).
   - evidence[] MUST be a flat list like:
     [{{"path":"invoice.total_amount","line_no":1}}, ...]
   - Use exact JSON paths from input; do not write vague evidence.

============================================================
AMOUNT RULES (STRICT)
============================================================
Goal: determine gross/net/vat consistently.

- Prefer explicit values in input priority:
  Priority A: if input.vat_amount exists and > 0 AND input.total_amount exists -> use them.
  Priority B: if vat_amount missing but vat_rate exists AND total_amount exists:
     If input.total_amount_includes_vat == true:
        net_amount = round(total_amount / (1 + vat_rate))
        vat_amount = total_amount - net_amount
     Else:
        net_amount = total_amount
        vat_amount = round(total_amount * vat_rate)
  Priority C: if ambiguous or missing -> needs_human_review=true

- Always enforce:
  gross_amount = net_amount + vat_amount

- If totals are inconsistent (difference > rounding tolerance):
  -> needs_human_review=true
  -> add risk explaining mismatch

============================================================
ACCOUNTING RULES (VAS DEFAULT)
============================================================
Use Vietnam VAS style default patterns when invoice_type is known:

A) SALES / AR invoice (revenue)
   - Debit: 131 (Accounts receivable)
   - Credit: 511 (Revenue) for net_amount
   - Credit: 3331 (VAT output) for vat_amount (if vat_amount > 0)

B) PURCHASE / AP invoice (inventory/service)
   - Credit: 331 (Accounts payable) for gross_amount
   - Debit: 152/156 (Inventory) OR 642 (Expense) depending on goods/service indicator
   - Debit: 1331 (VAT input) for vat_amount (if deductible and vat_amount > 0)

If invoice type cannot be reliably determined:
- needs_human_review=true
- still propose best-guess entries but mark risks clearly.

============================================================
CHART OF ACCOUNTS RULE (NON-NEGOTIABLE)
============================================================
- If input.chart_of_accounts exists:
  -> You MUST only use accounts that exist in that list.
  -> If required account missing -> needs_human_review=true and explain.

- If chart_of_accounts not provided:
  -> You may use default VAS accounts: 131, 331, 511, 3331, 1331, 152, 156, 642.

============================================================
QUALITY RULES (REAL ERP EXPECTATION)
============================================================
Confidence scoring:
- 0.90+ : invoice has total_amount + vat_amount + invoice_type clear + accounts valid + evidence complete
- 0.60–0.89 : partial info but still consistent
- <0.60 : unclear or missing critical fields -> needs_human_review=true

Always add risks if:
- missing invoice_date / invoice_number / seller_name
- VAT ambiguous
- totals mismatch
- invoice_type uncertain
- chart_of_accounts validation fails

============================================================
OUTPUT JSON SCHEMA (EXACT)
============================================================
{{
  "invoice_id": "...",
  "tenant_id": "...",
  "trace_id": "...",
  "needs_human_review": false,
  "confidence": 0.0,
  "risks": [],
  "assumptions": [],
  "evidence_fields_used": [],
  "explanation": "",
  "suggested_entries": [
    {{
      "line_no": 1,
      "debit_account": "131",
      "debit_account_name": null,
      "credit_account": "511",
      "credit_account_name": null,
      "amount": 0,
      "currency": "VND",
      "description": "Revenue",
      "evidence_fields": ["invoice.total_amount"]
    }}
  ],
  "evidence": [
    {{"path":"invoice.total_amount","line_no":1}}
  ]
}}

REMEMBER: OUTPUT JSON ONLY.
"""


# ==============================================================================
# API CLIENT
# ==============================================================================


def call_do_agent(invoice_json: dict[str, Any]) -> dict[str, Any]:
    """
    Call DigitalOcean Agent API (Qwen3-32B) to generate accounting proposal.

    Args:
        invoice_json: Dictionary containing invoice data with fields:
            - invoice_id, tenant_id, trace_id
            - invoice_no, date, total, vat, grand_total
            - doc_type, vat_rate, items, raw_text

    Returns:
        Dictionary with proposal data including:
            - needs_human_review, confidence
            - suggested_entries[], risks[], assumptions[]
            - evidence_fields_used[]

    Raises:
        ValueError: If API key or URL not configured
        RuntimeError: If API call fails
    """
    config = get_do_agent_config()

    # Validate configuration
    if not config["url"]:
        raise ValueError("DO_AGENT_URL not configured")
    if not config["key"]:
        raise ValueError("DO_AGENT_KEY not configured")

    # Log masked config (NEVER log full key)
    logger.info(
        f"DO Agent call: model={config['model']}, url={config['url'][:30]}..., key=...{mask_secret(config['key'])}"
    )

    # Build API request
    endpoint = f"{config['url'].rstrip('/')}/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
    }

    # Format user prompt with invoice data
    user_prompt = USER_PROMPT_TEMPLATE.format(invoice_json=json.dumps(invoice_json, ensure_ascii=False, indent=2))

    payload = {
        "model": config["model"],
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        "temperature": 0.3,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},  # Force JSON mode if supported
    }

    try:
        logger.info(f"Calling DO Agent API: {endpoint}")

        response = requests.post(endpoint, headers=headers, json=payload, timeout=config["timeout"])

        # Check HTTP status
        if response.status_code != 200:
            error_msg = f"DO Agent API error: {response.status_code} - {response.text[:200]}"
            logger.error(error_msg)
            return _error_response(invoice_json, error_msg)

        # Parse response
        result = response.json()

        # Extract content from OpenAI-compatible response
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0].get("message", {}).get("content", "")
        else:
            content = result.get("content", "")

        logger.info(f"DO Agent response length: {len(content)} chars")

        # Parse JSON from content
        return _parse_llm_json(content, invoice_json)

    except requests.Timeout:
        error_msg = f"DO Agent API timeout after {config['timeout']}s"
        logger.error(error_msg)
        return _error_response(invoice_json, error_msg)

    except requests.RequestException as e:
        error_msg = f"DO Agent API request failed: {str(e)}"
        logger.error(error_msg)
        return _error_response(invoice_json, error_msg)

    except Exception as e:
        error_msg = f"DO Agent unexpected error: {str(e)}"
        logger.error(error_msg)
        return _error_response(invoice_json, error_msg)


def _parse_llm_json(content: str, invoice_json: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON from LLM response, handling edge cases."""
    try:
        # Clean response - remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Try direct JSON parse
        parsed = json.loads(content)

        # Validate and normalize suggested_entries format
        entries = parsed.get("suggested_entries", [])
        normalized_entries = []
        evidence_flat = []
        all_evidence_fields = set()

        for i, entry in enumerate(entries):
            line_no = entry.get("line_no", i + 1)
            evidence_fields = entry.get("evidence_fields", [])

            # Collect evidence for flat list
            for path in evidence_fields:
                evidence_flat.append({"path": path, "line_no": line_no})
                all_evidence_fields.add(path)

            normalized_entry = {
                "line_no": line_no,
                "debit_account": str(entry.get("debit_account", "")),
                "debit_account_name": entry.get("debit_account_name"),
                "credit_account": str(entry.get("credit_account", "")),
                "credit_account_name": entry.get("credit_account_name"),
                "amount": float(entry.get("amount", 0)),
                "currency": entry.get("currency", "VND"),
                "description": entry.get("description", ""),
                "evidence_fields": evidence_fields,
            }
            normalized_entries.append(normalized_entry)

        # Merge with any explicit evidence_fields_used from LLM
        evidence_fields_used = list(all_evidence_fields.union(set(parsed.get("evidence_fields_used", []))))

        # Merge with any explicit evidence[] from LLM response
        llm_evidence = parsed.get("evidence", [])
        if llm_evidence:
            existing_paths = {(e["path"], e["line_no"]) for e in evidence_flat}
            for ev in llm_evidence:
                key = (ev.get("path", ""), ev.get("line_no", 0))
                if key not in existing_paths:
                    evidence_flat.append(ev)

        # Validate required fields and add defaults
        result = {
            "invoice_id": parsed.get("invoice_id", invoice_json.get("invoice_id", "")),
            "tenant_id": parsed.get("tenant_id", invoice_json.get("tenant_id", "")),
            "trace_id": parsed.get("trace_id", invoice_json.get("trace_id", "")),
            "needs_human_review": parsed.get("needs_human_review", False),
            "confidence": float(parsed.get("confidence", 0.75)),
            "suggested_entries": normalized_entries,
            "explanation": parsed.get("explanation", ""),
            "risks": parsed.get("risks", []),
            "assumptions": parsed.get("assumptions", []),
            "evidence_fields_used": evidence_fields_used,
            "evidence": evidence_flat,
            "llm_provider": "do_agent",
            "llm_model": get_do_agent_config()["model"],
            "llm_used": True,
            "parse_success": True,
        }

        logger.info(
            f"DO Agent JSON parsed successfully: {len(result['suggested_entries'])} entries, confidence={result['confidence']}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse DO Agent JSON: {e}")
        logger.debug(f"Raw content: {content[:500]}...")
        return _error_response(invoice_json, f"JSON parse error: {str(e)}")


def _error_response(invoice_json: dict[str, Any], error_msg: str) -> dict[str, Any]:
    """Generate error response that requires human review."""
    return {
        "invoice_id": invoice_json.get("invoice_id", ""),
        "tenant_id": invoice_json.get("tenant_id", ""),
        "trace_id": invoice_json.get("trace_id", ""),
        "needs_human_review": True,
        "confidence": 0.0,
        "suggested_entries": [],
        "explanation": f"Error: {error_msg}",
        "risks": [error_msg],
        "assumptions": [],
        "evidence_fields_used": [],
        "evidence": [],
        "llm_provider": "do_agent",
        "llm_model": get_do_agent_config()["model"],
        "llm_used": True,
        "parse_success": False,
    }


def is_do_agent_enabled() -> bool:
    """Check if DO Agent is configured and enabled."""
    config = get_do_agent_config()
    return config["provider"].lower() == "do_agent" and bool(config["url"]) and bool(config["key"])


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    # Test with sample invoice
    test_invoice = {
        "invoice_id": "test-001",
        "tenant_id": "demo-tenant",
        "trace_id": "trace-test-001",
        "invoice_no": "INV-2024-001",
        "date": "2024-01-15",
        "doc_type": "sales_invoice",
        "total": 25000000,
        "vat": 2500000,
        "grand_total": 27500000,
        "vat_rate": 0.1,
        "total_amount_includes_vat": False,
    }

    if is_do_agent_enabled():
        print("DO Agent is enabled, calling API...")
        result = call_do_agent(test_invoice)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("DO Agent is NOT enabled. Set environment variables:")
        print("  export LLM_PROVIDER=do_agent")
        print("  export DO_AGENT_URL=https://your-agent-url")
        print("  export DO_AGENT_KEY=your-api-key")
