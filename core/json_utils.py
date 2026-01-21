"""
ERPX AI Accounting - JSON Extraction & Repair Utilities
========================================================
Utilities for extracting and repairing JSON from LLM outputs.
No external dependencies beyond stdlib.
"""

import json
import re
from typing import Any


def extract_json_block(text: str) -> str | None:
    """
    Extract JSON from text that may contain markdown code fences or extra text.

    Priority:
    1. ```json ... ``` code fence
    2. ``` ... ``` generic code fence
    3. Raw JSON object/array by brace matching

    Args:
        text: Raw text potentially containing JSON

    Returns:
        Extracted JSON string or None if not found
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()

    # Priority 1: ```json ... ``` fence
    json_fence_match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if json_fence_match:
        return json_fence_match.group(1).strip()

    # Priority 2: ``` ... ``` generic fence
    generic_fence_match = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if generic_fence_match:
        content = generic_fence_match.group(1).strip()
        # Only return if it looks like JSON
        if content.startswith(("{", "[")):
            return content

    # Priority 3: Find JSON object by brace matching
    # Find first { or [
    obj_start = -1
    arr_start = -1

    for i, c in enumerate(text):
        if c == "{" and obj_start < 0:
            obj_start = i
            break
        if c == "[" and arr_start < 0:
            arr_start = i
            break

    # Try object extraction first (more common for LLM output)
    if obj_start >= 0:
        result = _extract_balanced(text, obj_start, "{", "}")
        if result:
            return result

    # Try array extraction
    if arr_start >= 0:
        result = _extract_balanced(text, arr_start, "[", "]")
        if result:
            return result

    return None


def _extract_balanced(text: str, start: int, open_char: str, close_char: str) -> str | None:
    """Extract substring with balanced braces/brackets."""
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        c = text[i]

        if escape_next:
            escape_next = False
            continue

        if c == "\\":
            escape_next = True
            continue

        if c == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def repair_json_light(text: str) -> str:
    """
    Light JSON repair for common LLM output issues.

    Handles:
    - BOM / null chars / control characters
    - Leading garbage before { or [
    - Smart quotes → standard quotes
    - Trailing commas before } or ]
    - Unescaped newlines in strings (basic)

    Args:
        text: Potentially broken JSON string

    Returns:
        Repaired JSON string (may still be invalid)
    """
    if not text or not isinstance(text, str):
        return text or ""

    # 1. Strip BOM and null chars
    result = text.lstrip("\ufeff\ufffe")
    result = result.replace("\x00", "")
    result = result.replace("\r\n", "\n")
    result = result.replace("\r", "\n")

    # 2. Remove control characters except newline/tab
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result)

    # 3. Strip leading garbage before { or [
    first_brace = -1
    for i, c in enumerate(result):
        if c in "{[":
            first_brace = i
            break

    if first_brace > 0:
        result = result[first_brace:]

    # 4. Replace smart quotes with standard quotes
    smart_quote_map = {
        """: '"',
        """: '"',
        "'": "'",
        "„": '"',
        "‟": '"',
        "‛": "'",
        "❝": '"',
        "❞": '"',
        "❮": '"',
        "❯": '"',
    }
    for smart, standard in smart_quote_map.items():
        result = result.replace(smart, standard)

    # 5. Remove trailing commas before } or ]
    # Pattern: comma followed by optional whitespace and } or ]
    result = re.sub(r",(\s*[}\]])", r"\1", result)

    # 6. Try to fix common issues with property names
    # Add quotes to unquoted property names (simple cases only)
    # Pattern: { or , followed by whitespace and identifier without quotes
    result = re.sub(
        r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)",
        r'\1"\2"\3',
        result,
    )

    return result.strip()


def safe_json_loads(text: str) -> tuple[Any | None, str | None]:
    """
    Safely parse JSON with error details.

    Args:
        text: JSON string to parse

    Returns:
        Tuple of (parsed_object, error_message)
        - On success: (obj, None)
        - On failure: (None, error_description)
    """
    if not text or not isinstance(text, str):
        return None, "Empty or non-string input"

    try:
        obj = json.loads(text)
        return obj, None
    except json.JSONDecodeError as e:
        # Provide helpful error context
        line = e.lineno
        col = e.colno
        pos = e.pos
        preview_start = max(0, pos - 20)
        preview_end = min(len(text), pos + 20)
        context = text[preview_start:preview_end]

        return None, f"JSON parse error at line {line}, col {col}: {e.msg}. Context: ...{context}..."
    except Exception as e:
        return None, f"Unexpected error: {type(e).__name__}: {e}"


def try_parse_json_robust(text: str) -> tuple[Any | None, str | None, str]:
    """
    Robust JSON parsing with multiple strategies.

    Attempts:
    1. Direct json.loads
    2. Extract JSON block, then parse
    3. Light repair, then parse

    Args:
        text: Raw text potentially containing JSON

    Returns:
        Tuple of (parsed_object, error_message, stage)
        - stage: "direct" | "extract" | "repair" | "failed"
    """
    if not text:
        return None, "Empty input", "failed"

    text = text.strip()

    # Stage 1: Direct parse
    obj, err = safe_json_loads(text)
    if obj is not None:
        return obj, None, "direct"

    # Stage 2: Extract JSON block
    block = extract_json_block(text)
    if block:
        obj, err = safe_json_loads(block)
        if obj is not None:
            return obj, None, "extract"

    # Stage 3: Light repair on block (or original)
    candidate = block or text
    repaired = repair_json_light(candidate)
    obj, err = safe_json_loads(repaired)
    if obj is not None:
        return obj, None, "repair"

    # All strategies failed
    return None, err or "All parse strategies failed", "failed"


def validate_json_schema_minimal(
    data: dict[str, Any],
    required_fields: list[str],
    field_types: dict[str, type] | None = None,
) -> tuple[bool, list[str]]:
    """
    Minimal schema validation without external dependencies.

    Args:
        data: Parsed JSON object
        required_fields: List of required field names
        field_types: Optional dict mapping field names to expected types

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not isinstance(data, dict):
        return False, ["Root must be an object/dict"]

    # Check required fields
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check field types if specified
    if field_types:
        for field, expected_type in field_types.items():
            if field in data:
                value = data[field]
                # Handle None values
                if value is None:
                    continue
                # Handle numeric coercion
                if expected_type in (int, float) and isinstance(value, (int, float, str)):
                    try:
                        float(value)  # Test if convertible
                        continue
                    except (ValueError, TypeError):
                        pass
                # Handle list type
                if expected_type is list and isinstance(value, list):
                    continue
                # Standard type check
                if not isinstance(value, expected_type):
                    errors.append(f"Field '{field}' expected {expected_type.__name__}, got {type(value).__name__}")

    return len(errors) == 0, errors


def coerce_numeric_fields(
    data: dict[str, Any],
    numeric_fields: list[str],
) -> dict[str, Any]:
    """
    Coerce string values to numeric for specified fields.

    Args:
        data: Parsed JSON object
        numeric_fields: List of field names that should be numeric

    Returns:
        Modified data dict with coerced values
    """
    if not isinstance(data, dict):
        return data

    result = data.copy()

    for field in numeric_fields:
        if field in result and isinstance(result[field], str):
            try:
                # Try int first, then float
                val = result[field].strip()
                if "." in val or "," in val:
                    result[field] = float(val.replace(",", ""))
                else:
                    result[field] = int(val)
            except (ValueError, TypeError):
                pass  # Keep original value

    return result
