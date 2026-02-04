"""
ERPX AI Accounting - Input Validator
====================================
Validates input data before processing.
Implements R1 (Scope Lock) and input safety checks.
"""

import os
import re
import sys
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ValidationResult:
    """Result of input validation"""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    sanitized_input: dict[str, Any] | None = None
    scope_violation: bool = False
    sanitized_content: str | None = None


class InputValidator:
    """
    Input validation and sanitization.

    Checks:
    - Required fields present
    - Data types correct
    - Size limits respected
    - No injection attacks
    - Scope lock (R1) - only accounting operations
    """

    # Maximum sizes
    MAX_OCR_TEXT_LENGTH = 100000  # 100KB
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    MAX_ITEMS_COUNT = 1000
    MAX_FIELD_LENGTH = 10000

    # Dangerous patterns (injection prevention)
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>",  # XSS
        r"javascript:",
        r"data:text/html",
        r"on\w+\s*=",  # Event handlers
        r"--\s*$",  # SQL comment
        r";\s*DROP\s+",  # SQL injection
        r"UNION\s+SELECT",
        r"\$\{.*\}",  # Template injection
        r"\{\{.*\}\}",
        r"ignore\s+previous\s+instructions",
    ]

    # Out-of-scope keywords (R1 - Scope Lock)
    OUT_OF_SCOPE_KEYWORDS = [
        "marketing campaign",
        "social media",
        "hr payroll",
        "crm customer",
        "web scraping",
        "send email",
        "chatbot conversation",
    ]

    def __init__(self):
        self._dangerous_regex = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]

    def validate(self, content: str = None, doc_type: str = None) -> ValidationResult:
        """
        Backwards-compatible validator used by unit tests.
        Treats `content` as OCR text and applies scope lock + sanitization.
        """
        result = self.validate_coding_request(ocr_text=content, structured_fields=None, file_content=None, mode="STRICT")
        scope_violation = any("Scope Lock" in err for err in result.errors)
        sanitized_content = self._sanitize_text(content) if content else ""
        sanitized_input = result.sanitized_input or {"ocr_text": sanitized_content, "doc_type": doc_type}
        if doc_type and isinstance(sanitized_input, dict):
            sanitized_input["doc_type"] = doc_type
        return ValidationResult(
            is_valid=result.is_valid,
            errors=result.errors,
            warnings=result.warnings,
            sanitized_input=sanitized_input,
            scope_violation=scope_violation,
            sanitized_content=sanitized_content,
        )

    def validate_coding_request(
        self,
        ocr_text: str = None,
        structured_fields: dict[str, Any] = None,
        file_content: bytes = None,
        mode: str = "STRICT",
    ) -> ValidationResult:
        """
        Validate a coding request.

        Returns ValidationResult with is_valid flag and any errors/warnings.
        """
        errors = []
        warnings = []

        # Check at least one input provided
        if not any([ocr_text, structured_fields, file_content]):
            errors.append("At least one input required: ocr_text, structured_fields, or file_content")

        # Validate OCR text
        if ocr_text:
            ocr_errors, ocr_warnings = self._validate_text(ocr_text, "ocr_text")
            errors.extend(ocr_errors)
            warnings.extend(ocr_warnings)

        # Validate structured fields
        if structured_fields:
            struct_errors, struct_warnings = self._validate_structured(structured_fields)
            errors.extend(struct_errors)
            warnings.extend(struct_warnings)

        # Validate file content
        if file_content:
            file_errors, file_warnings = self._validate_file(file_content)
            errors.extend(file_errors)
            warnings.extend(file_warnings)

        # Validate mode
        if mode and mode.upper() not in ["STRICT", "RELAXED"]:
            errors.append(f"Invalid mode: {mode}. Must be STRICT or RELAXED")

        # Check scope (R1)
        scope_errors = self._check_scope(ocr_text, structured_fields)
        errors.extend(scope_errors)

        # Build sanitized input
        sanitized = None
        if not errors:
            sanitized = {
                "ocr_text": self._sanitize_text(ocr_text) if ocr_text else None,
                "structured_fields": self._sanitize_dict(structured_fields) if structured_fields else None,
                "mode": mode.upper() if mode else "STRICT",
            }

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, sanitized_input=sanitized)

    def _validate_text(self, text: str, field_name: str) -> tuple[list[str], list[str]]:
        """Validate text field"""
        errors = []
        warnings = []

        if not isinstance(text, str):
            errors.append(f"{field_name} must be a string")
            return errors, warnings

        # Size check
        if len(text) > self.MAX_OCR_TEXT_LENGTH:
            errors.append(f"{field_name} exceeds maximum length ({self.MAX_OCR_TEXT_LENGTH})")

        # Dangerous pattern check
        for pattern in self._dangerous_regex:
            if pattern.search(text):
                warnings.append(f"Potentially dangerous pattern detected in {field_name}")
                break

        return errors, warnings

    def _validate_structured(self, data: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Validate structured fields"""
        errors = []
        warnings = []

        if not isinstance(data, dict):
            errors.append("structured_fields must be a dictionary")
            return errors, warnings

        # Check field sizes
        for key, value in data.items():
            if isinstance(value, str) and len(value) > self.MAX_FIELD_LENGTH:
                errors.append(f"Field '{key}' exceeds maximum length")

            if isinstance(value, list) and len(value) > self.MAX_ITEMS_COUNT:
                errors.append(f"Field '{key}' has too many items (max {self.MAX_ITEMS_COUNT})")

        # Validate known field types
        if "grand_total" in data:
            if not self._is_numeric(data["grand_total"]):
                errors.append("grand_total must be numeric")

        if "vat_amount" in data:
            if not self._is_numeric(data["vat_amount"]):
                errors.append("vat_amount must be numeric")

        if "items" in data:
            if not isinstance(data["items"], list):
                errors.append("items must be a list")

        return errors, warnings

    def _validate_file(self, content: bytes) -> tuple[list[str], list[str]]:
        """Validate file content"""
        errors = []
        warnings = []

        if not isinstance(content, bytes):
            errors.append("file_content must be bytes")
            return errors, warnings

        if len(content) > self.MAX_FILE_SIZE_BYTES:
            errors.append(f"File exceeds maximum size ({self.MAX_FILE_SIZE_BYTES} bytes)")

        # Check file signature for allowed types
        allowed_signatures = [
            b"%PDF",  # PDF
            b"\x89PNG",  # PNG
            b"\xff\xd8\xff",  # JPEG
            b"{",  # JSON (starts with {)
            b"[",  # JSON array
        ]

        is_allowed = any(content.startswith(sig) for sig in allowed_signatures)
        if not is_allowed:
            # Check if it's plain text
            try:
                content[:1000].decode("utf-8")
            except:
                warnings.append("File type may not be supported")

        return errors, warnings

    def _check_scope(self, ocr_text: str, structured_fields: dict) -> list[str]:
        """
        Check R1 - Scope Lock.
        Ensure request is within accounting scope.
        """
        errors = []

        # Combine text for checking
        text_to_check = ""
        if ocr_text:
            text_to_check += ocr_text.lower()
        if structured_fields:
            text_to_check += " " + str(structured_fields).lower()

        # Check for out-of-scope keywords
        for keyword in self.OUT_OF_SCOPE_KEYWORDS:
            if keyword in text_to_check:
                errors.append(f"R1 Scope Lock: Request appears to be outside accounting scope (detected: {keyword})")
                break

        return errors

    def _is_numeric(self, value: Any) -> bool:
        """Check if value is numeric"""
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.replace(",", ""))
                return True
            except:
                pass
        return False

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text input"""
        if not text:
            return ""

        # Remove null bytes
        text = text.replace("\x00", "")

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove dangerous patterns (simple version)
        for pattern in self._dangerous_regex:
            text = pattern.sub("", text)

        return text.strip()

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize dictionary input"""
        if not data:
            return {}

        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            safe_key = re.sub(r"[^\w_]", "", str(key))[:100]

            # Sanitize value
            if isinstance(value, str):
                sanitized[safe_key] = self._sanitize_text(value)
            elif isinstance(value, dict):
                sanitized[safe_key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[safe_key] = [
                    self._sanitize_dict(v) if isinstance(v, dict) else v for v in value[: self.MAX_ITEMS_COUNT]
                ]
            else:
                sanitized[safe_key] = value

        return sanitized


def validate_coding_request(
    ocr_text: str = None, structured_fields: dict[str, Any] = None, file_content: bytes = None, mode: str = "STRICT"
) -> ValidationResult:
    """Convenience function for input validation"""
    validator = InputValidator()
    return validator.validate_coding_request(
        ocr_text=ocr_text, structured_fields=structured_fields, file_content=file_content, mode=mode
    )


if __name__ == "__main__":
    # Test input validator
    validator = InputValidator()

    # Valid input
    result = validator.validate_coding_request(ocr_text="Invoice #123 Total: 1,000,000 VND", mode="STRICT")
    print(f"Valid input: is_valid={result.is_valid}, errors={result.errors}")

    # Invalid - empty
    result = validator.validate_coding_request()
    print(f"Empty input: is_valid={result.is_valid}, errors={result.errors}")

    # Out of scope (R1)
    result = validator.validate_coding_request(ocr_text="Please send email marketing campaign to customers")
    print(f"Out of scope: is_valid={result.is_valid}, errors={result.errors}")

    # Invalid mode
    result = validator.validate_coding_request(ocr_text="Invoice #123", mode="INVALID")
    print(f"Invalid mode: is_valid={result.is_valid}, errors={result.errors}")
