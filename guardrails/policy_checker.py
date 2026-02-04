"""
ERPX AI Accounting - Policy Checker
===================================
Implements business policy rules and approval gates (R6).
"""

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import (
    APPROVAL_THRESHOLD_AUTO,
    APPROVAL_THRESHOLD_MANAGER,
    DOC_TYPE_RECEIPT,
    DOC_TYPE_VAT_INVOICE,
    MODE_STRICT,
)


class ApprovalLevel(str, Enum):
    """Approval level required"""

    AUTO = "auto"
    CLERK = "clerk"
    MANAGER = "manager"
    DIRECTOR = "director"


@dataclass
class PolicyCheckResult:
    """Result of policy check"""

    passed: bool
    requires_review: bool
    approval_level: ApprovalLevel
    violations: list[str]
    recommendations: list[str]


@dataclass
class ApprovalDecision:
    """Compatibility result for unit tests"""

    needs_approval: bool
    approval_reasons: list[str]
    vat_compliant: bool
    approver_level: str


class PolicyChecker:
    """
    Business policy checker for accounting operations.

    Implements R6 - Approval Gate logic.
    """

    def __init__(self, mode: str = MODE_STRICT, tenant_config: dict = None):
        self.mode = mode.upper()
        self.tenant_config = tenant_config or {}

        # Configurable thresholds (can be overridden per tenant)
        self.auto_approval_threshold = self.tenant_config.get("auto_approval_threshold", APPROVAL_THRESHOLD_AUTO)
        self.manager_approval_threshold = self.tenant_config.get(
            "manager_approval_threshold", APPROVAL_THRESHOLD_MANAGER
        )

    def check(
        self,
        amount: float,
        doc_type: str = None,
        vendor_id: str | None = None,
        is_new_vendor: bool = False,
        vat_rate: float | None = None,
        has_vat_invoice: bool | None = None,
    ) -> ApprovalDecision:
        """
        Backwards-compatible check used by unit tests.
        """
        approval_reasons: list[str] = []
        needs_approval = False

        if amount is None:
            amount = 0

        # Amount-based approval gate
        if amount > self.auto_approval_threshold:
            needs_approval = True
            approval_reasons.append("amount exceeds auto-approval threshold")

        # New vendor policy
        if is_new_vendor or (vendor_id and vendor_id.upper().startswith("NEW")):
            needs_approval = True
            approval_reasons.append("new vendor requires approval")

        # VAT compliance
        vat_compliant = True
        if vat_rate is not None and vat_rate not in [0, 5, 8, 10]:
            vat_compliant = False
            approval_reasons.append("invalid VAT rate")
            needs_approval = True

        if has_vat_invoice is False and amount >= 20_000_000:
            vat_compliant = False
            approval_reasons.append("missing VAT invoice for high-value transaction")
            needs_approval = True

        # Approver level (simplified)
        if amount > self.manager_approval_threshold:
            approver_level = "manager"
        elif amount > self.auto_approval_threshold:
            approver_level = "kế toán trưởng"
        else:
            approver_level = "auto"

        return ApprovalDecision(
            needs_approval=needs_approval,
            approval_reasons=approval_reasons,
            vat_compliant=vat_compliant,
            approver_level=approver_level,
        )

    def check_policy(self, output: dict[str, Any], context: dict[str, Any] = None) -> PolicyCheckResult:
        """
        Check if output passes business policies.

        Args:
            output: Accounting coding output
            context: Additional context (user, department, etc.)

        Returns:
            PolicyCheckResult with approval requirements
        """
        violations = []
        recommendations = []
        requires_review = False
        approval_level = ApprovalLevel.AUTO

        payload = output.get("asof_payload", {})
        doc_type = payload.get("doc_type")
        chi_tiet = payload.get("chi_tiet", {})
        grand_total = chi_tiet.get("grand_total") or 0
        missing_fields = output.get("missing_fields", [])

        # Policy 1: Amount-based approval
        amount_level = self._check_amount_threshold(grand_total)
        if amount_level.value > approval_level.value:
            approval_level = amount_level
            if amount_level != ApprovalLevel.AUTO:
                recommendations.append(f"Amount {grand_total:,.0f} VND requires {amount_level.value} approval")

        # Policy 2: Missing required fields (STRICT mode)
        if self.mode == MODE_STRICT:
            field_violations = self._check_required_fields(doc_type, missing_fields)
            violations.extend(field_violations)
            if field_violations:
                requires_review = True

        # Policy 3: VAT compliance
        vat_violations = self._check_vat_compliance(payload)
        violations.extend(vat_violations)
        if vat_violations:
            requires_review = True

        # Policy 4: Document type specific rules
        doctype_violations = self._check_doctype_rules(doc_type, payload)
        violations.extend(doctype_violations)
        if doctype_violations:
            requires_review = True

        # Policy 5: High-risk indicators
        risk_violations = self._check_risk_indicators(payload, context)
        violations.extend(risk_violations)
        if risk_violations:
            requires_review = True
            approval_level = max(approval_level, ApprovalLevel.MANAGER, key=lambda x: x.value)

        # Determine final status
        passed = len(violations) == 0

        return PolicyCheckResult(
            passed=passed,
            requires_review=requires_review or not passed,
            approval_level=approval_level,
            violations=violations,
            recommendations=recommendations,
        )

    def _check_amount_threshold(self, amount: float) -> ApprovalLevel:
        """Determine approval level based on amount"""
        if amount <= 0:
            return ApprovalLevel.AUTO

        if amount <= self.auto_approval_threshold:
            return ApprovalLevel.AUTO
        elif amount <= self.manager_approval_threshold:
            return ApprovalLevel.MANAGER
        else:
            return ApprovalLevel.DIRECTOR

    def _check_required_fields(self, doc_type: str, missing_fields: list[str]) -> list[str]:
        """Check required fields based on document type"""
        violations = []

        if doc_type == DOC_TYPE_VAT_INVOICE:
            # VAT invoice requires specific fields
            critical_missing = [
                f for f in missing_fields if f in ["invoice_serial", "invoice_no", "invoice_date", "tax_id"]
            ]

            if critical_missing:
                violations.append(f"VAT invoice missing critical fields: {critical_missing}")

        elif doc_type == DOC_TYPE_RECEIPT:
            # Receipts have relaxed requirements
            if "grand_total" in missing_fields:
                violations.append("Receipt missing grand_total")

        return violations

    def _check_vat_compliance(self, payload: dict[str, Any]) -> list[str]:
        """Check VAT compliance rules"""
        violations = []

        thue = payload.get("thue", {})
        chi_tiet = payload.get("chi_tiet", {})

        vat_rate = thue.get("vat_rate")
        vat_amount = thue.get("vat_amount")
        grand_total = chi_tiet.get("grand_total")
        subtotal = chi_tiet.get("subtotal")

        # Check VAT calculation consistency
        if all(v is not None for v in [vat_rate, subtotal, vat_amount]):
            expected_vat = subtotal * (vat_rate / 100)
            if abs(expected_vat - vat_amount) > 100:  # 100 VND tolerance
                violations.append(f"VAT calculation inconsistent: expected {expected_vat:.0f}, got {vat_amount:.0f}")

        # Check total consistency
        if all(v is not None for v in [subtotal, vat_amount, grand_total]):
            expected_total = subtotal + vat_amount
            if abs(expected_total - grand_total) > 100:
                violations.append(f"Total inconsistent: {subtotal} + {vat_amount} != {grand_total}")

        # Check tax account is set for VAT transactions
        if vat_amount and vat_amount > 0:
            if not thue.get("tax_account"):
                violations.append("VAT amount present but tax_account not set")

        return violations

    def _check_doctype_rules(self, doc_type: str, payload: dict[str, Any]) -> list[str]:
        """Check document type specific rules"""
        violations = []

        hoa_don = payload.get("hoa_don", {})

        if doc_type == DOC_TYPE_VAT_INVOICE:
            # VAT invoice serial format (Vietnamese e-invoice)
            serial = hoa_don.get("invoice_serial")
            if serial:
                # Check format: 1C24TAA, 2C24TAB, etc.
                import re

                if not re.match(r"^[12][A-Z]\d{2}[A-Z]{3}$", serial):
                    violations.append(f"Invalid invoice serial format: {serial} (expected: 1C24TAA)")

            # Tax ID format (Vietnamese MST)
            tax_id = hoa_don.get("tax_id")
            if tax_id:
                # Remove dashes
                clean_tax_id = tax_id.replace("-", "")
                if not re.match(r"^\d{10}$|^\d{13}$", clean_tax_id):
                    violations.append(f"Invalid tax ID format: {tax_id} (expected: 10 or 13 digits)")

        return violations

    def _check_risk_indicators(self, payload: dict[str, Any], context: dict[str, Any] = None) -> list[str]:
        """Check for high-risk indicators"""
        violations = []
        context = context or {}

        chi_tiet = payload.get("chi_tiet", {})
        chung_tu = payload.get("chung_tu", {})

        # Risk 1: Round numbers (potential fabrication)
        grand_total = chi_tiet.get("grand_total")
        if grand_total and grand_total > 1000000:
            # Check if suspiciously round
            if grand_total % 1000000 == 0:
                violations.append(f"Suspicious round amount: {grand_total:,.0f} VND")

        # Risk 2: Foreign currency without approval
        currency = chung_tu.get("currency", "VND")
        if currency != "VND" and not context.get("forex_approved"):
            violations.append(f"Foreign currency transaction ({currency}) requires special approval")

        # Risk 3: Vendor not in approved list
        vendor = chung_tu.get("customer_or_vendor")
        approved_vendors = context.get("approved_vendors", [])
        if vendor and approved_vendors and vendor not in approved_vendors:
            violations.append(f"Vendor '{vendor}' not in approved vendor list")

        return violations


def check_policy(
    output: dict[str, Any], mode: str = MODE_STRICT, context: dict[str, Any] = None, tenant_config: dict = None
) -> PolicyCheckResult:
    """Convenience function for policy checking"""
    checker = PolicyChecker(mode=mode, tenant_config=tenant_config)
    return checker.check_policy(output, context)


if __name__ == "__main__":
    # Test policy checker
    checker = PolicyChecker(mode=MODE_STRICT)

    # Test 1: Valid small receipt
    output1 = {
        "asof_payload": {
            "doc_type": "receipt",
            "chung_tu": {"currency": "VND"},
            "hoa_don": {},
            "thue": {"vat_amount": 10000, "vat_rate": 10},
            "chi_tiet": {"subtotal": 100000, "grand_total": 110000},
        },
        "missing_fields": [],
    }

    result = checker.check_policy(output1)
    print(f"Small receipt: passed={result.passed}, level={result.approval_level.value}")
    print(f"  Violations: {result.violations}")

    # Test 2: Large VAT invoice
    output2 = {
        "asof_payload": {
            "doc_type": "vat_invoice",
            "chung_tu": {"currency": "VND", "customer_or_vendor": "ABC Corp"},
            "hoa_don": {"invoice_serial": "1C24TAA", "invoice_no": "0001", "tax_id": "0102030405"},
            "thue": {"vat_amount": 5000000, "vat_rate": 10, "tax_account": "13311"},
            "chi_tiet": {"subtotal": 50000000, "grand_total": 55000000},
        },
        "missing_fields": [],
    }

    result = checker.check_policy(output2)
    print(f"\nLarge VAT invoice: passed={result.passed}, level={result.approval_level.value}")
    print(f"  Violations: {result.violations}")
    print(f"  Recommendations: {result.recommendations}")

    # Test 3: Invalid VAT invoice (missing fields)
    output3 = {
        "asof_payload": {
            "doc_type": "vat_invoice",
            "chung_tu": {},
            "hoa_don": {},
            "thue": {},
            "chi_tiet": {"grand_total": 1000000},
        },
        "missing_fields": ["invoice_serial", "invoice_no", "tax_id"],
    }

    result = checker.check_policy(output3)
    print(f"\nInvalid VAT invoice: passed={result.passed}, requires_review={result.requires_review}")
    print(f"  Violations: {result.violations}")
