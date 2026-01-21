"""
ERPX AI Accounting - LLM Output Schemas
=======================================
Pydantic models for validating LLM-generated JSON output.
Used to ensure proper shape before downstream processing.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class JournalEntryLine(BaseModel):
    """Single journal entry line from LLM output."""

    account_code: str = Field(..., description="Account code from chart of accounts")
    account_name: str = Field(default="", description="Account name")
    debit: float = Field(default=0, ge=0, description="Debit amount")
    credit: float = Field(default=0, ge=0, description="Credit amount")
    description: str | None = Field(default=None, description="Line description")

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        """Coerce string values to float."""
        if v is None:
            return 0
        if isinstance(v, str):
            try:
                return float(v.replace(",", "").strip())
            except (ValueError, TypeError):
                return 0
        return float(v) if v else 0

    @model_validator(mode="after")
    def check_debit_credit(self):
        """Ensure line doesn't have both debit and credit > 0."""
        if self.debit > 0 and self.credit > 0:
            # Auto-fix: use net amount
            if self.debit > self.credit:
                self.debit = self.debit - self.credit
                self.credit = 0
            else:
                self.credit = self.credit - self.debit
                self.debit = 0
        return self


class LLMInvoiceExtraction(BaseModel):
    """
    Schema for LLM invoice extraction output.

    This is the expected shape from generate_json() for invoice processing.
    """

    doc_type: str = Field(
        default="other",
        description="Document type: purchase_invoice, sales_invoice, expense, other",
    )
    vendor: str | None = Field(default=None, description="Vendor/supplier name")
    invoice_no: str | None = Field(default=None, description="Invoice number")
    invoice_date: str | None = Field(default=None, description="Invoice date (YYYY-MM-DD)")
    total_amount: float = Field(default=0, ge=0, description="Total amount")
    vat_amount: float = Field(default=0, ge=0, description="VAT amount")
    entries: list[JournalEntryLine] = Field(
        default_factory=list,
        min_length=0,
        description="Journal entry lines",
    )
    explanation: str | None = Field(default=None, description="LLM explanation")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence score")
    needs_human_review: bool = Field(default=False, description="Requires human review")
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    doc_id: str | None = Field(default=None, description="Document/job ID")

    @field_validator("total_amount", "vat_amount", mode="before")
    @classmethod
    def coerce_amount(cls, v):
        """Coerce string amounts to float."""
        if v is None:
            return 0
        if isinstance(v, str):
            try:
                return float(v.replace(",", "").strip())
            except (ValueError, TypeError):
                return 0
        return float(v) if v else 0

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v):
        """Coerce confidence to valid range."""
        if v is None:
            return 0.5
        try:
            val = float(v)
            return max(0, min(1, val))
        except (ValueError, TypeError):
            return 0.5

    @field_validator("doc_type", mode="before")
    @classmethod
    def normalize_doc_type(cls, v):
        """Normalize document type."""
        if not v:
            return "other"
        v_lower = str(v).lower().strip()
        valid_types = ["purchase_invoice", "sales_invoice", "expense", "other"]
        # Fuzzy matching
        if "purchase" in v_lower or "mua" in v_lower:
            return "purchase_invoice"
        if "sale" in v_lower or "bán" in v_lower:
            return "sales_invoice"
        if "expense" in v_lower or "chi phí" in v_lower:
            return "expense"
        if v_lower in valid_types:
            return v_lower
        return "other"

    def is_balanced(self) -> bool:
        """Check if journal entries are balanced."""
        total_debit = sum(e.debit for e in self.entries)
        total_credit = sum(e.credit for e in self.entries)
        return abs(total_debit - total_credit) < 0.01

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for downstream processing."""
        return self.model_dump()


def validate_llm_output(data: dict[str, Any]) -> tuple[LLMInvoiceExtraction | None, list[str]]:
    """
    Validate LLM output against schema.

    Args:
        data: Raw dict from LLM JSON parsing

    Returns:
        Tuple of (validated_model, list_of_errors)
        - On success: (model, [])
        - On failure: (None, [error_messages])
    """
    errors = []

    try:
        model = LLMInvoiceExtraction.model_validate(data)

        # Additional business validations
        if not model.entries:
            errors.append("No journal entries provided")

        if not model.is_balanced():
            total_debit = sum(e.debit for e in model.entries)
            total_credit = sum(e.credit for e in model.entries)
            errors.append(f"Journal entries not balanced: debit={total_debit}, credit={total_credit}")

        if errors:
            # Return model but with warnings
            model.needs_human_review = True
            model.risks.extend(errors)
            return model, errors

        return model, []

    except Exception as e:
        return None, [f"Schema validation failed: {e}"]


def coerce_and_validate(data: dict[str, Any]) -> dict[str, Any]:
    """
    Coerce and validate LLM output, returning cleaned dict.

    This is a convenience function that returns a dict suitable for
    downstream processing, even if validation has warnings.

    Args:
        data: Raw dict from LLM

    Returns:
        Cleaned and validated dict
    """
    model, errors = validate_llm_output(data)

    if model is None:
        # Return original data with error markers
        data["_validation_errors"] = errors
        data["needs_human_review"] = True
        return data

    result = model.to_dict()
    if errors:
        result["_validation_warnings"] = errors

    return result
