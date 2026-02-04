"""
ERPX AI Accounting - LangGraph Workflow
=======================================
Implements the accounting workflow as a state machine.
Steps: A(Ingest) → B(Classify) → C(Extract) → D(Validate) → E(Reconcile) → F(Decision)
"""

import json
import logging
import os
import re
import sys
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import (
    APPROVAL_THRESHOLD_AUTO,
    DOC_TYPE_BANK_SLIP,
    DOC_TYPE_OTHER,
    DOC_TYPE_RECEIPT,
    DOC_TYPE_VAT_INVOICE,
    DocumentType,
    MODE_STRICT,
    RECONCILIATION_AMOUNT_TOLERANCE_PERCENT,
    RECONCILIATION_AMOUNT_TOLERANCE_VND,
    RECONCILIATION_DATE_WINDOW_DAYS,
)
from orchestrator.states import ValidationStatus, WorkflowState, WorkflowStep

logger = logging.getLogger("erpx.orchestrator.workflow")


class AccountingWorkflow:
    """
    LangGraph-style state machine for accounting document processing.

    Workflow Steps:
    A. Ingest & Normalize - Parse input, normalize text
    B. Doc Type Classification - Determine document type
    C. Field Extraction - Extract structured fields
    D. Validation & Policy - Check required fields, apply rules
    E. Bank Reconciliation - Match with bank transactions
    F. Final Decision - Set approval flags
    """

    def __init__(self, mode: str = MODE_STRICT, tenant_id: str = None):
        self.mode = mode.upper()
        self.tenant_id = tenant_id
        self.state: WorkflowState | None = None

        # Node handlers
        self.nodes: dict[WorkflowStep, Callable] = {
            WorkflowStep.INGEST: self._step_a_ingest,
            WorkflowStep.CLASSIFY: self._step_b_classify,
            WorkflowStep.EXTRACT: self._step_c_extract,
            WorkflowStep.VALIDATE: self._step_d_validate,
            WorkflowStep.RECONCILE: self._step_e_reconcile,
            WorkflowStep.DECISION: self._step_f_decision,
        }

    def run(
        self,
        ocr_text: str = None,
        structured_fields: dict[str, Any] = None,
        file_metadata: dict[str, Any] = None,
        bank_txns: list[dict[str, Any]] = None,
        doc_id: str = None,
    ) -> dict[str, Any]:
        """
        Execute the complete workflow.

        Returns the final output conforming to FIXED SCHEMA (R7).
        """
        # Initialize state
        self.state = WorkflowState(
            doc_id=doc_id or str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            request_id=str(uuid.uuid4()),
            mode=self.mode,
            raw_input=ocr_text,
            structured_input=structured_fields,
            file_metadata=file_metadata or {},
            bank_transactions=bank_txns,
            started_at=datetime.utcnow().isoformat(),
        )

        try:
            # Execute workflow steps in order
            for step in [
                WorkflowStep.INGEST,
                WorkflowStep.CLASSIFY,
                WorkflowStep.EXTRACT,
                WorkflowStep.VALIDATE,
                WorkflowStep.RECONCILE,
                WorkflowStep.DECISION,
            ]:
                # Skip reconciliation if no bank transactions
                if step == WorkflowStep.RECONCILE and not bank_txns:
                    self.state.record_step(step, {"skipped": True, "reason": "no_bank_txns"})
                    continue

                # Execute step
                handler = self.nodes.get(step)
                if handler:
                    self.state.record_step(step)
                    handler()
                    logger.debug(f"Completed step {step.value}")

                # Check for errors
                if self.state.error_message:
                    break

            # Mark complete
            self.state.current_step = WorkflowStep.COMPLETE
            self.state.completed_at = datetime.utcnow().isoformat()

            # Build final output
            return self._build_output()

        except Exception as e:
            logger.error(f"Workflow error: {str(e)}")
            self.state.error_message = str(e)
            self.state.error_step = self.state.current_step.value
            self.state.current_step = WorkflowStep.ERROR
            return self._build_output()

    # =========================================================================
    # STEP A: INGEST & NORMALIZE
    # =========================================================================

    def _step_a_ingest(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step A: Ingest & Normalize
        - Parse raw input or structured input
        - Normalize text (strip, clean whitespace)
        - Extract text blocks for later processing
        """
        if state is not None:
            self.state = state
        state = self.state

        # Determine input source
        if state.raw_input:
            # OCR text input
            state.normalized_text = self._normalize_text(state.raw_input)
            state.text_blocks = self._split_text_blocks(state.normalized_text)
            state.add_evidence("input_source", "ocr_text", "input", state.normalized_text[:200])

        elif state.structured_input:
            # Structured JSON input
            # Extract text if available in structured data
            ocr_text = state.structured_input.get("ocr_text", "")
            if ocr_text:
                state.normalized_text = self._normalize_text(ocr_text)
                state.text_blocks = self._split_text_blocks(state.normalized_text)
            else:
                state.normalized_text = json.dumps(state.structured_input, indent=2)
                state.text_blocks = [state.normalized_text]
            state.add_evidence("input_source", "structured", "input", str(state.structured_input)[:200])

        else:
            state.add_error("No input provided (ocr_text or structured_fields required)")
            state.error_message = "No input data"
            state.has_error = True

        logger.debug(f"Ingest complete: {len(state.text_blocks or [])} blocks")
        if not state.error_message:
            state.current_step = WorkflowStep.CLASSIFY
        return state

    def _normalize_text(self, text: str) -> str:
        """Normalize text: strip, reduce whitespace"""
        if not text:
            return ""
        # Reduce multiple spaces/newlines
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_text_blocks(self, text: str) -> list[str]:
        """Split text into logical blocks"""
        if not text:
            return []
        # Split by double newlines or sentence-like boundaries
        blocks = re.split(r"\n\n+|\.\s+", text)
        return [b.strip() for b in blocks if b.strip()]

    # =========================================================================
    # STEP B: DOCUMENT TYPE CLASSIFICATION
    # =========================================================================

    def _step_b_classify(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step B: Document Type Classification
        - Determine if receipt, VAT invoice, bank slip, or other
        - R4: Doc-Type Truth - Don't mis-classify
        """
        if state is not None:
            self.state = state
        state = self.state
        text = (state.normalized_text or state.raw_input or state.raw_content or "").lower()
        structured = state.structured_input or {}
        doc_type_map = {
            DOC_TYPE_VAT_INVOICE: DocumentType.INVOICE.value,
            DOC_TYPE_BANK_SLIP: DocumentType.BANK_STATEMENT.value,
        }

        # Check structured data first
        if "doc_type" in structured:
            state.doc_type = doc_type_map.get(structured["doc_type"], structured["doc_type"])
            state.doc_type_confidence = 1.0
            state.add_evidence("doc_type", state.doc_type, "structured", "Explicit doc_type field")
            state.current_step = WorkflowStep.EXTRACT
            return state

        # Classify based on keywords
        vat_keywords = [
            "hóa đơn gtgt",
            "hóa đơn giá trị gia tăng",
            "vat invoice",
            "mst:",
            "mã số thuế",
            "serial:",
            "ký hiệu:",
        ]
        receipt_keywords = ["receipt", "phiếu thu", "biên lai", "pos", "total:", "tổng cộng:"]
        bank_keywords = ["bank statement", "sao kê ngân hàng", "sào kê ngân hàng", "giao dịch ngân hàng", "bank transaction"]

        vat_score = sum(1 for k in vat_keywords if k in text)
        receipt_score = sum(1 for k in receipt_keywords if k in text)
        bank_score = sum(1 for k in bank_keywords if k in text)

        # Check for structured invoice indicators
        if structured.get("invoice_serial") or structured.get("tax_id"):
            vat_score += 2
        if structured.get("store") or (structured.get("company") not in ["", None]):
            receipt_score += 1

        # Determine type
        if vat_score > receipt_score and vat_score > bank_score:
            state.doc_type = DOC_TYPE_VAT_INVOICE
            state.doc_type_confidence = min(0.5 + vat_score * 0.1, 0.95)
            evidence = [k for k in vat_keywords if k in text][:3]
        elif bank_score > receipt_score:
            state.doc_type = DOC_TYPE_BANK_SLIP
            state.doc_type_confidence = min(0.5 + bank_score * 0.1, 0.95)
            evidence = [k for k in bank_keywords if k in text][:3]
        elif receipt_score > 0:
            state.doc_type = DOC_TYPE_RECEIPT
            state.doc_type_confidence = min(0.5 + receipt_score * 0.1, 0.95)
            evidence = [k for k in receipt_keywords if k in text][:3]
        else:
            state.doc_type = DOC_TYPE_OTHER
            state.doc_type_confidence = 0.3
            evidence = ["No clear classification keywords found"]

        state.classification_evidence = evidence
        state.doc_type = doc_type_map.get(state.doc_type, state.doc_type)
        state.add_evidence("doc_type", state.doc_type, "inferred", f"Keywords: {evidence}")

        logger.debug(f"Classification: {state.doc_type} (confidence: {state.doc_type_confidence})")
        state.current_step = WorkflowStep.EXTRACT
        return state

    # =========================================================================
    # STEP C: FIELD EXTRACTION
    # =========================================================================

    def _step_c_extract(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step C: Field Extraction
        - Extract all fields from OCR text and structured input
        - R2: No Hallucination - Only extract what's present
        - R3: Amount/Date Integrity - Verbatim extraction
        """
        if state is not None:
            self.state = state
        state = self.state
        text = state.normalized_text or state.raw_input or state.raw_content or ""
        structured = state.structured_input or {}

        extracted = {}

        # ===== CHUNG_TU (Document Header) =====
        extracted["chung_tu"] = {
            "posting_date": self._extract_date(text, structured, "posting_date"),
            "doc_date": self._extract_date(text, structured, "doc_date", "date"),
            "customer_or_vendor": self._extract_field(
                text, structured, "company", "vendor", "customer_or_vendor", "store"
            ),
            "description": self._extract_field(text, structured, "description", "memo"),
            "currency": self._extract_field(text, structured, "currency") or "VND",
        }

        # ===== HOA_DON (Invoice Info) =====
        extracted["hoa_don"] = {
            "invoice_serial": self._extract_field(text, structured, "invoice_serial", "serial"),
            "invoice_no": self._extract_field(text, structured, "invoice_no", "receipt_no", "number"),
            "invoice_date": self._extract_date(text, structured, "invoice_date", "date"),
            "invoice_type": state.doc_type,
            "tax_id": self._extract_field(text, structured, "tax_id", "mst", "vat_number"),
        }

        # ===== THUE (Tax Info) =====
        vat_amount = self._extract_number(text, structured, "vat_amount", "tax_amount", "vat")
        grand_total = self._extract_number(text, structured, "grand_total", "total", "amount")
        subtotal = self._extract_number(text, structured, "subtotal", "sub_total")

        # Infer VAT rate if possible
        vat_rate = self._extract_number(text, structured, "vat_rate", "tax_rate")
        if vat_rate is None and vat_amount and subtotal and subtotal > 0:
            # Calculate VAT rate from amounts
            calculated_rate = (vat_amount / subtotal) * 100
            if abs(calculated_rate - 10) < 1:
                vat_rate = 10.0
            elif abs(calculated_rate - 8) < 1:
                vat_rate = 8.0
            elif abs(calculated_rate - 5) < 1:
                vat_rate = 5.0

        extracted["thue"] = {
            "vat_rate": vat_rate,
            "vat_amount": vat_amount,
            "tax_account": self._extract_field(text, structured, "tax_account"),
            "tax_group": self._extract_field(text, structured, "tax_group"),
        }

        # ===== CHI_TIET (Line Items) =====
        items = self._extract_line_items(text, structured)
        extracted["chi_tiet"] = {"items": items, "subtotal": subtotal, "grand_total": grand_total}

        state.extracted_fields = extracted
        state.extracted_data = extracted
        logger.debug(f"Extraction complete: {len(extracted)} sections")
        state.current_step = WorkflowStep.VALIDATE
        return state

    def _extract_field(self, text: str, structured: dict, *field_names) -> str | None:
        """Extract a field value from structured data or text"""
        # Try structured data first
        for name in field_names:
            if name in structured and structured[name]:
                self.state.add_evidence(field_names[0], structured[name], "structured", f"Field: {name}")
                return str(structured[name])

        # No text extraction for generic fields (R2: No Hallucination)
        return None

    def _extract_date(self, text: str, structured: dict, *field_names) -> str | None:
        """Extract a date field - R3: Date Integrity"""
        # Try structured data
        for name in field_names:
            if name in structured and structured[name]:
                date_val = structured[name]
                self.state.add_evidence(field_names[0], date_val, "structured", f"Date field: {name}")
                return str(date_val)

        # Try to find date patterns in text
        date_patterns = [
            r"\b(\d{2}/\d{2}/\d{4})\b",  # dd/mm/yyyy
            r"\b(\d{4}-\d{2}-\d{2})\b",  # yyyy-mm-dd
            r"\b(\d{2}-\d{2}-\d{4})\b",  # dd-mm-yyyy
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_val = match.group(1)
                self.state.add_evidence(field_names[0], date_val, "ocr", f"Pattern match: {date_val}")
                return date_val

        return None

    def _extract_number(self, text: str, structured: dict, *field_names) -> float | None:
        """Extract a numeric field - R3: Amount Integrity"""
        # Try structured data first
        for name in field_names:
            if name in structured and structured[name] is not None:
                try:
                    val = float(structured[name])
                    self.state.add_evidence(field_names[0], val, "structured", f"Number field: {name}")
                    return val
                except (ValueError, TypeError):
                    pass

        # Don't extract numbers from text to avoid hallucination (R2)
        return None

    def _extract_line_items(self, text: str, structured: dict) -> list[dict[str, Any]]:
        """Extract line items from structured data"""
        items = []

        # Check for items in structured data
        if "items" in structured and isinstance(structured["items"], list):
            for i, item in enumerate(structured["items"]):
                line_item = {
                    "line_no": i + 1,
                    "item_code": item.get("item_code"),
                    "description": item.get("description", item.get("name")),
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("unit_price", item.get("price")),
                    "amount": item.get("amount", item.get("total")),
                    "vat_rate": item.get("vat_rate"),
                    "vat_amount": item.get("vat_amount"),
                }
                items.append(line_item)

        return items

    # =========================================================================
    # STEP D: VALIDATION & POLICY CHECK
    # =========================================================================

    def _step_d_validate(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step D: Validation & Policy Check
        - Check required fields based on doc_type and mode
        - R4: Doc-Type Truth handling
        - R6: Approval Gate preparation
        """
        if state is not None:
            self.state = state
        state = self.state
        extracted = state.extracted_fields

        # Determine required fields based on doc_type and mode
        if state.doc_type in (DOC_TYPE_VAT_INVOICE, DocumentType.INVOICE.value):
            if self.mode == MODE_STRICT:
                required = ["invoice_serial", "invoice_no", "invoice_date", "tax_id", "tax_account", "tax_group"]
            else:
                required = ["invoice_serial", "invoice_no"]  # Relaxed: minimum VAT fields
        elif state.doc_type == DOC_TYPE_RECEIPT:
            # Receipts have relaxed requirements - R4
            required = ["grand_total"] if self.mode == MODE_STRICT else []
        else:
            required = []

        # Check required fields
        missing = []
        for field in required:
            value = self._get_nested_field(extracted, field)
            if value is None:
                missing.append(field)

        state.missing_fields = missing

        # Validate amounts
        chi_tiet = extracted.get("chi_tiet", {})
        grand_total = chi_tiet.get("grand_total")
        subtotal = chi_tiet.get("subtotal")
        vat_amount = extracted.get("thue", {}).get("vat_amount")

        # Check amount consistency (if all values present)
        if grand_total and subtotal and vat_amount:
            expected_total = subtotal + vat_amount
            if abs(expected_total - grand_total) > 1:  # Allow 1 VND rounding
                state.add_warning(f"Amount mismatch: subtotal({subtotal}) + VAT({vat_amount}) != total({grand_total})")

        # Set validation status
        if missing and self.mode == MODE_STRICT:
            if state.doc_type == DOC_TYPE_VAT_INVOICE:
                state.validation_status = ValidationStatus.FAIL
                state.add_error(f"Missing required VAT invoice fields: {missing}")
            else:
                state.validation_status = ValidationStatus.WARN
                state.add_warning(f"Missing fields: {missing}")
        elif state.validation_warnings:
            state.validation_status = ValidationStatus.WARN
        else:
            state.validation_status = ValidationStatus.PASS

        state.validation_result = {
            "is_valid": state.validation_status != ValidationStatus.FAIL,
            "errors": state.validation_errors,
            "warnings": state.validation_warnings,
        }

        logger.debug(f"Validation: {state.validation_status.value}, missing: {missing}")
        state.current_step = WorkflowStep.RECONCILE if state.bank_transactions else WorkflowStep.DECISION
        return state

    def _get_nested_field(self, data: dict, field: str) -> Any:
        """Get a field from nested dict structure"""
        # Map field names to their locations
        field_map = {
            "invoice_serial": ("hoa_don", "invoice_serial"),
            "invoice_no": ("hoa_don", "invoice_no"),
            "invoice_date": ("hoa_don", "invoice_date"),
            "tax_id": ("hoa_don", "tax_id"),
            "tax_account": ("thue", "tax_account"),
            "tax_group": ("thue", "tax_group"),
            "grand_total": ("chi_tiet", "grand_total"),
            "subtotal": ("chi_tiet", "subtotal"),
            "vat_amount": ("thue", "vat_amount"),
            "posting_date": ("chung_tu", "posting_date"),
            "doc_date": ("chung_tu", "doc_date"),
        }

        if field in field_map:
            section, key = field_map[field]
            return data.get(section, {}).get(key)

        return data.get(field)

    # =========================================================================
    # STEP E: BANK RECONCILIATION
    # =========================================================================

    def _step_e_reconcile(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step E: Bank Reconciliation
        - Match invoices with bank transactions
        - Apply tolerance rules: ±0.5% or ±50,000 VND, ±7 days
        """
        if state is not None:
            self.state = state
        state = self.state
        bank_txns = state.bank_transactions or []

        if not bank_txns:
            logger.debug("No bank transactions to reconcile")
            state.current_step = WorkflowStep.DECISION
            return state

        extracted = state.extracted_fields
        invoice_total = extracted.get("chi_tiet", {}).get("grand_total")
        invoice_date_str = extracted.get("hoa_don", {}).get("invoice_date")
        invoice_vendor = extracted.get("chung_tu", {}).get("customer_or_vendor", "")
        invoice_no = extracted.get("hoa_don", {}).get("invoice_no", "")

        matches = []
        used_txn_ids = set()

        for txn in bank_txns:
            txn_id = txn.get("txn_id")
            txn_amount = txn.get("amount")
            txn_date_str = txn.get("txn_date")
            txn_memo = txn.get("memo", "")

            # Calculate match score
            score = 0.0
            reasons = []

            # Amount matching
            if invoice_total and txn_amount:
                amount_diff = abs(invoice_total - txn_amount)
                percent_diff = (amount_diff / invoice_total * 100) if invoice_total > 0 else 100

                if amount_diff == 0:
                    score += 0.5
                    reasons.append("exact_amount_match")
                elif percent_diff <= RECONCILIATION_AMOUNT_TOLERANCE_PERCENT:
                    score += 0.4
                    reasons.append(f"amount_within_{RECONCILIATION_AMOUNT_TOLERANCE_PERCENT}%")
                elif amount_diff <= RECONCILIATION_AMOUNT_TOLERANCE_VND:
                    score += 0.3
                    reasons.append(f"amount_within_{RECONCILIATION_AMOUNT_TOLERANCE_VND}VND")

            # Date matching
            if invoice_date_str and txn_date_str:
                try:
                    invoice_date = self._parse_date(invoice_date_str)
                    txn_date = self._parse_date(txn_date_str)
                    if invoice_date and txn_date:
                        days_diff = abs((txn_date - invoice_date).days)
                        if days_diff == 0:
                            score += 0.3
                            reasons.append("exact_date_match")
                        elif days_diff <= RECONCILIATION_DATE_WINDOW_DAYS:
                            score += 0.2
                            reasons.append(f"date_within_{RECONCILIATION_DATE_WINDOW_DAYS}_days")
                except:
                    pass

            # Keyword matching (vendor, invoice_no in memo)
            if txn_memo:
                memo_lower = txn_memo.lower()
                if invoice_vendor and invoice_vendor.lower() in memo_lower:
                    score += 0.15
                    reasons.append("vendor_in_memo")
                if invoice_no and invoice_no in memo_lower:
                    score += 0.15
                    reasons.append("invoice_no_in_memo")

            # Minimum threshold for match
            if score >= 0.5 and txn_id not in used_txn_ids:
                matches.append(
                    {
                        "invoice_id": state.doc_id,
                        "txn_id": txn_id,
                        "match_score": round(score, 2),
                        "reason": ", ".join(reasons),
                        "amount_diff": round(invoice_total - txn_amount, 2) if invoice_total and txn_amount else 0,
                    }
                )
                used_txn_ids.add(txn_id)

        # Sort by score and take best match
        matches.sort(key=lambda x: x["match_score"], reverse=True)

        state.reconciliation_matches = matches[:1]  # Best match only
        state.unmatched_bank_txns = [t["txn_id"] for t in bank_txns if t["txn_id"] not in used_txn_ids]

        if not matches:
            state.unmatched_invoices = [state.doc_id]
            state.add_warning("No matching bank transaction found")

        logger.debug(f"Reconciliation: {len(matches)} matches found")
        state.current_step = WorkflowStep.DECISION
        return state

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse date string to datetime"""
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        return None

    # =========================================================================
    # STEP F: FINAL DECISION
    # =========================================================================

    def _step_f_decision(self, state: WorkflowState | None = None) -> WorkflowState:
        """
        Step F: Final Decision
        - Set needs_human_review flag
        - R6: Approval Gate logic
        """
        if state is not None:
            self.state = state
        state = self.state

        # Conditions requiring human review
        if state.validation_status == ValidationStatus.FAIL:
            state.mark_for_review("Validation failed")

        if state.missing_fields and state.doc_type == DOC_TYPE_VAT_INVOICE and self.mode == MODE_STRICT:
            state.mark_for_review(f"Missing required fields: {state.missing_fields}")

        if state.doc_type_confidence < 0.5:
            state.mark_for_review(f"Low classification confidence: {state.doc_type_confidence}")

        # Check amount threshold
        chi_tiet = state.extracted_fields.get("chi_tiet")
        grand_total = chi_tiet.get("grand_total") if isinstance(chi_tiet, dict) else state.extracted_fields.get("grand_total")
        if grand_total and grand_total > APPROVAL_THRESHOLD_AUTO:
            state.mark_for_review(f"Amount exceeds auto-approval threshold: {grand_total}")
            state.approval_threshold_exceeded = True

        # Reconciliation issues
        if state.bank_transactions and not state.reconciliation_matches:
            state.add_warning("No bank transaction match - manual reconciliation needed")

        state.output = self._build_output()
        state.current_step = WorkflowStep.DECISION

        logger.debug(f"Decision: needs_review={state.needs_human_review}, reasons={state.review_reasons}")
        return state

    # =========================================================================
    # OUTPUT BUILDER
    # =========================================================================

    def _build_output(self) -> dict[str, Any]:
        """
        Build the final output conforming to FIXED SCHEMA (R7).
        """
        state = self.state
        extracted = state.extracted_fields or {}

        # Build evidence
        key_snippets = []
        numbers_found = []

        for ev in state.evidence_log:
            if ev.get("snippet"):
                key_snippets.append(ev["snippet"][:100])
            if isinstance(ev.get("value"), (int, float)):
                numbers_found.append({"label": ev["field"], "value": ev["value"], "source": ev["source"]})

        # Build workflow trace
        workflow_trace = [f"{entry.get('step', 'unknown')}" for entry in state.step_history]

        return {
            "asof_payload": {
                "doc_type": state.doc_type or DOC_TYPE_OTHER,
                "chung_tu": extracted.get("chung_tu", {}),
                "hoa_don": extracted.get("hoa_don", {}),
                "thue": extracted.get("thue", {}),
                "chi_tiet": extracted.get("chi_tiet", {}),
            },
            "reconciliation_result": {
                "matched": state.reconciliation_matches,
                "unmatched_invoices": state.unmatched_invoices,
                "unmatched_bank_txns": state.unmatched_bank_txns,
            },
            "needs_human_review": state.needs_human_review,
            "missing_fields": state.missing_fields,
            "warnings": state.validation_warnings + (state.validation_errors if state.validation_errors else []),
            "evidence": {"key_text_snippets": key_snippets[:10], "numbers_found": numbers_found[:20]},
            "source_file": state.file_metadata.get("source_file") if state.file_metadata else None,
            "doc_id": state.doc_id,
            "processed_at": datetime.utcnow().isoformat(),
            "processing_mode": self.mode,
            "workflow_trace": workflow_trace,
        }


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ERPX Accounting Workflow")
    parser.add_argument("--input", "-i", help="Input JSON file")
    parser.add_argument("--mode", "-m", choices=["STRICT", "RELAXED"], default="STRICT")
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty print output")

    args = parser.parse_args()

    # Sample input
    sample_input = {
        "ocr_text": "RECEIPT Store: ABC Mart Date: 20/01/2026 Total: 150,000 VND",
        "doc_type": "receipt",
        "grand_total": 150000,
        "date": "20/01/2026",
        "store": "ABC Mart",
    }

    if args.input:
        with open(args.input) as f:
            sample_input = json.load(f)

    workflow = AccountingWorkflow(mode=args.mode)
    result = workflow.run(ocr_text=sample_input.get("ocr_text"), structured_fields=sample_input, doc_id="TEST-001")

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
