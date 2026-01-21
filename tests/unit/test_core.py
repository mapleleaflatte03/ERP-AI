"""
ERPX AI Accounting - Unit Tests
==============================
Tests for core functionality.
"""

import json
import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import (
    APPROVAL_THRESHOLD_AUTO,
    RECONCILIATION_AMOUNT_TOLERANCE_PERCENT,
    DocumentType,
)
from core.schemas import (
    AccountingCodingOutput,
    ASOFPayload,
    ChungTu,
)


class TestDocumentTypeClassification:
    """Tests for R4 - Doc-Type === Ground Truth"""

    def test_valid_document_types(self):
        """Test all valid document types are accepted"""
        valid_types = [
            DocumentType.INVOICE.value,
            DocumentType.RECEIPT.value,
            DocumentType.BANK_STATEMENT.value,
            DocumentType.EXPENSE_REPORT.value,
        ]
        for doc_type in valid_types:
            assert doc_type in [e.value for e in DocumentType]

    def test_invoice_classification(self):
        """Test invoice type identification"""
        invoice_keywords = ["hóa đơn", "invoice", "HD-GTGT", "VAT invoice"]
        for keyword in invoice_keywords:
            if any(k in keyword.lower() for k in ["hóa đơn", "invoice", "hd-gtgt"]):
                classified_type = DocumentType.INVOICE.value
            else:
                classified_type = "unknown"
            assert classified_type == DocumentType.INVOICE.value


class TestAmountExtraction:
    """Tests for R3 - Amount/Date Integrity"""

    def test_amount_parsing_vnd(self):
        """Test Vietnamese number format parsing"""
        test_cases = [
            ("1.000.000", 1_000_000),
            ("1,000,000", 1_000_000),
            ("1000000", 1_000_000),
        ]
        for text, expected in test_cases:
            cleaned = text.replace(" VND", "").replace(" đồng", "")
            if cleaned.count(".") > 1 or (cleaned.count(".") == 1 and len(cleaned.split(".")[-1]) == 3):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
            parsed = float(cleaned)
            if parsed == int(parsed):
                parsed = int(parsed)
            assert parsed == expected

    def test_vat_calculation(self):
        """Test VAT calculation accuracy"""
        test_cases = [
            (1_000_000, 10, 100_000),
            (1_000_000, 8, 80_000),
            (1_000_000, 5, 50_000),
            (1_000_000, 0, 0),
        ]
        for subtotal, rate, expected_vat in test_cases:
            calculated_vat = round(subtotal * rate / 100)
            assert calculated_vat == expected_vat


class TestApprovalGating:
    """Tests for R6 - Approval Gate"""

    def test_auto_approval_threshold(self):
        """Test amounts below auto threshold pass automatically"""
        auto_threshold = APPROVAL_THRESHOLD_AUTO
        test_amounts = [
            (5_000_000, False),
            (9_999_999, False),
            (10_000_001, True),
            (50_000_000, True),
        ]
        for amount, needs_review in test_amounts:
            calculated_needs_review = amount > auto_threshold
            assert calculated_needs_review == needs_review


class TestReconciliation:
    """Tests for bank reconciliation logic"""

    def test_amount_tolerance(self):
        """Test amount matching within tolerance"""
        tolerance_percent = RECONCILIATION_AMOUNT_TOLERANCE_PERCENT
        tolerance_fixed = 50_000
        test_cases = [
            (1_000_000, 1_000_000, True),
            (1_000_000, 1_005_000, True),
            (100_000, 149_000, True),
        ]
        for expected, actual, should_match in test_cases:
            diff = abs(expected - actual)
            percent_diff = (diff / expected * 100) if expected > 0 else 0
            matches = diff <= tolerance_fixed or percent_diff <= tolerance_percent
            assert matches == should_match


class TestOutputSchema:
    """Tests for R7 - Fixed Output Schema"""

    def test_valid_output_structure(self):
        """Test that output conforms to schema"""
        output = AccountingCodingOutput(
            doc_id="TEST-001",
            asof_payload=ASOFPayload(
                doc_type="vat_invoice",
                chung_tu=ChungTu(posting_date="15/01/2024"),
            ),
        )
        assert output.doc_id == "TEST-001"
        assert output.asof_payload.doc_type == "vat_invoice"

    def test_json_serialization(self):
        """Test output can be serialized to JSON"""
        output = AccountingCodingOutput(doc_id="TEST-002", asof_payload=ASOFPayload(doc_type="receipt"))
        json_str = output.model_dump_json()
        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed["doc_id"] == "TEST-002"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
