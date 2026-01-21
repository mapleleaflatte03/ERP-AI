"""
ERPX AI - Guardrails Module
============================
Input/Output validation for AI processing.

Features:
- Input validation (file type, size, content)
- Output validation (schema compliance, business rules)
- PII detection and masking
- Confidence thresholds
- OPA policy integration
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("erpx.guardrails")


# ===========================================================================
# Configuration
# ===========================================================================


@dataclass
class GuardrailsConfig:
    """Guardrails configuration"""

    # OPA endpoint
    opa_url: str = field(default_factory=lambda: os.getenv("OPA_URL", "http://opa:8181"))

    # Confidence thresholds
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.6"))
    human_review_threshold: float = float(os.getenv("HUMAN_REVIEW_THRESHOLD", "0.8"))

    # Input limits
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    max_text_length: int = int(os.getenv("MAX_TEXT_LENGTH", "50000"))

    # Output limits
    max_journal_entries: int = int(os.getenv("MAX_JOURNAL_ENTRIES", "20"))
    max_amount: float = float(os.getenv("MAX_AMOUNT", "1000000000"))  # 1 billion VND

    # PII patterns
    pii_detection_enabled: bool = os.getenv("PII_DETECTION_ENABLED", "true").lower() == "true"


# ===========================================================================
# Input Validators
# ===========================================================================


class InputValidator(ABC):
    """Base class for input validators"""

    @abstractmethod
    def validate(self, data: Any) -> tuple[bool, str]:
        """Return (is_valid, error_message)"""
        pass


class FileSizeValidator(InputValidator):
    """Validate file size"""

    def __init__(self, max_size_mb: int = 50):
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def validate(self, file_size: int) -> tuple[bool, str]:
        if file_size > self.max_size_bytes:
            return False, f"File size {file_size} exceeds max {self.max_size_bytes}"
        return True, ""


class FileTypeValidator(InputValidator):
    """Validate file type"""

    ALLOWED_TYPES = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/plain",
        "text/csv",
    ]

    def validate(self, content_type: str) -> tuple[bool, str]:
        if not any(allowed in content_type for allowed in self.ALLOWED_TYPES):
            return False, f"File type {content_type} not allowed"
        return True, ""


class TextLengthValidator(InputValidator):
    """Validate text length"""

    def __init__(self, max_length: int = 50000):
        self.max_length = max_length

    def validate(self, text: str) -> tuple[bool, str]:
        if len(text) > self.max_length:
            return False, f"Text length {len(text)} exceeds max {self.max_length}"
        return True, ""


class PIIValidator(InputValidator):
    """Detect and flag PII in text"""

    # Vietnamese PII patterns
    PATTERNS = {
        "cmnd": r"\b\d{9,12}\b",  # ID card number
        "phone": r"\b0[35789]\d{8}\b",  # Vietnamese phone
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "bank_account": r"\b\d{10,20}\b",  # Bank account number
        "tax_id": r"\b\d{10}(?:-\d{3})?\b",  # Tax ID (MST)
    }

    def validate(self, text: str) -> tuple[bool, str]:
        found_pii = []
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                found_pii.append(f"{pii_type}: {len(matches)} occurrences")

        if found_pii:
            return True, f"PII detected: {', '.join(found_pii)}"
        return True, ""


# ===========================================================================
# Output Validators
# ===========================================================================


class OutputValidator(ABC):
    """Base class for output validators"""

    @abstractmethod
    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        """Return (is_valid, error_message, warnings)"""
        pass


class SchemaValidator(OutputValidator):
    """Validate output schema"""

    REQUIRED_FIELDS = ["doc_type", "total_amount", "entries"]

    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        warnings = []

        # Check required fields
        missing = [f for f in self.REQUIRED_FIELDS if f not in data]
        if missing:
            return False, f"Missing required fields: {missing}", warnings

        # Validate doc_type
        valid_doc_types = ["purchase_invoice", "sales_invoice", "expense", "receipt", "other"]
        if data.get("doc_type") not in valid_doc_types:
            warnings.append(f"Unexpected doc_type: {data.get('doc_type')}")

        # Validate entries
        if not isinstance(data.get("entries"), list):
            return False, "entries must be a list", warnings

        return True, "", warnings


class BalanceValidator(OutputValidator):
    """Validate accounting balance (debit = credit)"""

    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        warnings = []
        entries = data.get("entries", [])

        total_debit = sum(float(e.get("debit", 0) or 0) for e in entries)
        total_credit = sum(float(e.get("credit", 0) or 0) for e in entries)

        if abs(total_debit - total_credit) > 0.01:
            return False, f"Unbalanced: Debit={total_debit}, Credit={total_credit}", warnings

        return True, "", warnings


class AmountValidator(OutputValidator):
    """Validate amount ranges"""

    def __init__(self, max_amount: float = 1000000000):
        self.max_amount = max_amount

    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        warnings = []

        total = float(data.get("total_amount", 0) or 0)
        if total < 0:
            return False, "total_amount cannot be negative", warnings

        if total > self.max_amount:
            warnings.append(f"Unusually high amount: {total:,.0f} VND")

        # Validate individual entries
        for i, entry in enumerate(data.get("entries", [])):
            debit = float(entry.get("debit", 0) or 0)
            credit = float(entry.get("credit", 0) or 0)

            if debit < 0 or credit < 0:
                return False, f"Entry {i}: negative amounts not allowed", warnings

        return True, "", warnings


class AccountCodeValidator(OutputValidator):
    """Validate Vietnamese accounting codes (TT200)"""

    # Valid account code prefixes (simplified)
    VALID_PREFIXES = [
        "111",
        "112",
        "113",  # Cash, Bank
        "121",
        "128",
        "131",
        "133",  # Receivables
        "141",
        "142",
        "151",
        "152",
        "153",
        "154",
        "155",
        "156",  # Inventory
        "211",
        "212",
        "213",
        "214",  # Fixed assets
        "217",
        "221",
        "228",
        "229",  # Long-term
        "241",
        "242",  # Construction
        "311",
        "331",
        "333",
        "334",
        "335",
        "336",  # Payables
        "341",
        "343",  # Long-term debt
        "411",
        "412",
        "413",
        "414",
        "418",
        "419",
        "421",  # Equity
        "461",
        "466",  # Reserves
        "511",
        "512",
        "515",  # Revenue
        "521",  # Discounts
        "611",
        "621",
        "622",
        "623",
        "627",  # Costs
        "631",
        "632",
        "635",
        "641",
        "642",  # Expenses
        "711",  # Other income
        "811",
        "821",  # Other expenses
        "911",  # Income summary
    ]

    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        warnings = []

        for i, entry in enumerate(data.get("entries", [])):
            code = str(entry.get("account_code", ""))

            if not code:
                warnings.append(f"Entry {i}: missing account_code")
                continue

            # Check if code matches valid prefixes
            valid = any(code.startswith(prefix) for prefix in self.VALID_PREFIXES)
            if not valid:
                warnings.append(f"Entry {i}: unrecognized account code {code}")

        return True, "", warnings


class ConfidenceValidator(OutputValidator):
    """Validate confidence and flag for human review"""

    def __init__(self, min_confidence: float = 0.6, review_threshold: float = 0.8):
        self.min_confidence = min_confidence
        self.review_threshold = review_threshold

    def validate(self, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
        warnings = []
        confidence = float(data.get("confidence", 0) or 0)

        if confidence < self.min_confidence:
            return False, f"Confidence {confidence} below minimum {self.min_confidence}", warnings

        if confidence < self.review_threshold:
            warnings.append(f"Low confidence ({confidence:.2f}), human review recommended")

        return True, "", warnings


# ===========================================================================
# OPA Policy Client
# ===========================================================================


class OPAClient:
    """Client for Open Policy Agent"""

    def __init__(self, opa_url: str = "http://opa:8181"):
        self.opa_url = opa_url
        self.client = httpx.Client(timeout=5.0)

    def evaluate(self, policy_path: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Evaluate OPA policy"""
        try:
            url = f"{self.opa_url}/v1/data/{policy_path}"
            response = self.client.post(url, json={"input": input_data})
            response.raise_for_status()
            return response.json().get("result", {})
        except Exception as e:
            logger.error(f"OPA evaluation failed: {e}")
            return {"allow": True, "error": str(e)}  # Fail open for now

    def check_document_access(self, user_id: str, doc_type: str, action: str) -> bool:
        """Check if user can access document"""
        result = self.evaluate("erpx/document_access", {"user_id": user_id, "doc_type": doc_type, "action": action})
        return result.get("allow", True)

    def check_approval_limit(self, user_id: str, amount: float) -> bool:
        """Check if user can approve amount"""
        result = self.evaluate("erpx/approval_limit", {"user_id": user_id, "amount": amount})
        return result.get("allow", True)


# ===========================================================================
# Main Guardrails Engine
# ===========================================================================


class GuardrailsEngine:
    """Main guardrails engine combining all validators"""

    def __init__(self, config: GuardrailsConfig | None = None):
        self.config = config or GuardrailsConfig()

        # Input validators
        self.input_validators = [
            ("file_size", FileSizeValidator(self.config.max_file_size_mb)),
            ("file_type", FileTypeValidator()),
            ("text_length", TextLengthValidator(self.config.max_text_length)),
        ]
        if self.config.pii_detection_enabled:
            self.input_validators.append(("pii", PIIValidator()))

        # Output validators
        self.output_validators = [
            ("schema", SchemaValidator()),
            ("balance", BalanceValidator()),
            ("amount", AmountValidator(self.config.max_amount)),
            ("account_code", AccountCodeValidator()),
            ("confidence", ConfidenceValidator(self.config.min_confidence, self.config.human_review_threshold)),
        ]

        # OPA client
        self.opa = OPAClient(self.config.opa_url)

    def validate_input(
        self, file_size: int | None = None, content_type: str | None = None, text: str | None = None
    ) -> tuple[bool, list[str], list[str]]:
        """
        Validate input data.

        Returns:
            (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        for name, validator in self.input_validators:
            try:
                if name == "file_size" and file_size is not None:
                    valid, msg = validator.validate(file_size)
                elif name == "file_type" and content_type is not None:
                    valid, msg = validator.validate(content_type)
                elif name in ["text_length", "pii"] and text is not None:
                    valid, msg = validator.validate(text)
                else:
                    continue

                if not valid:
                    errors.append(f"{name}: {msg}")
                elif msg:  # Warning
                    warnings.append(f"{name}: {msg}")

            except Exception as e:
                logger.error(f"Validator {name} failed: {e}")
                warnings.append(f"{name}: validation error")

        return len(errors) == 0, errors, warnings

    def validate_output(self, data: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        """
        Validate output data.

        Returns:
            (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        for name, validator in self.output_validators:
            try:
                valid, msg, warns = validator.validate(data)

                if not valid:
                    errors.append(f"{name}: {msg}")
                warnings.extend([f"{name}: {w}" for w in warns])

            except Exception as e:
                logger.error(f"Validator {name} failed: {e}")
                warnings.append(f"{name}: validation error")

        return len(errors) == 0, errors, warnings

    def process(self, input_data: dict[str, Any], output_data: dict[str, Any]) -> dict[str, Any]:
        """
        Full guardrails processing.

        Returns processed data with validation results.
        """
        result = {
            "input_validation": {},
            "output_validation": {},
            "overall_valid": True,
            "needs_human_review": False,
            "all_warnings": [],
            "all_errors": [],
        }

        # Validate input
        valid, errors, warnings = self.validate_input(
            file_size=input_data.get("file_size"),
            content_type=input_data.get("content_type"),
            text=input_data.get("text"),
        )
        result["input_validation"] = {"valid": valid, "errors": errors, "warnings": warnings}
        result["all_errors"].extend(errors)
        result["all_warnings"].extend(warnings)

        # Validate output
        valid, errors, warnings = self.validate_output(output_data)
        result["output_validation"] = {"valid": valid, "errors": errors, "warnings": warnings}
        result["all_errors"].extend(errors)
        result["all_warnings"].extend(warnings)

        # Determine overall status
        result["overall_valid"] = len(result["all_errors"]) == 0
        result["needs_human_review"] = (
            len(result["all_warnings"]) > 0
            or output_data.get("needs_human_review", False)
            or output_data.get("confidence", 1.0) < self.config.human_review_threshold
        )

        return result


# ===========================================================================
# Singleton instance
# ===========================================================================

_engine: GuardrailsEngine | None = None


def get_guardrails_engine() -> GuardrailsEngine:
    """Get or create guardrails engine"""
    global _engine
    if _engine is None:
        _engine = GuardrailsEngine()
    return _engine


# ===========================================================================
# Convenience functions
# ===========================================================================


def validate_document_input(file_size: int, content_type: str, text: str | None = None) -> tuple[bool, list[str]]:
    """Quick input validation"""
    engine = get_guardrails_engine()
    valid, errors, _ = engine.validate_input(file_size, content_type, text)
    return valid, errors


def validate_proposal_output(data: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """Quick output validation"""
    engine = get_guardrails_engine()
    return engine.validate_output(data)
