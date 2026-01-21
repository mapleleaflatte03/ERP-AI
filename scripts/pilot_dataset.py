#!/usr/bin/env python3
"""
Pilot Dataset Generator with Ground Truth
==========================================
Generates 30 synthetic invoices with balanced scenarios + expected_entries.

Each invoice includes:
- invoice data (like real OCR output)
- _expected_entries: deterministic rule-based ground truth for validation
- _scenario: test scenario label

Scenarios (30 total):
- 5x sales/vat_10
- 3x sales/vat_0
- 2x sales/vat_exempt
- 2x sales/missing_vat
- 2x sales/rounding_mismatch
- 5x purchase/vat_10
- 3x purchase/vat_0
- 2x purchase/vat_exempt
- 2x purchase/missing_total
- 2x purchase/rounding_mismatch
- 2x sales/high_value
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# VAS-correct expected entries generators
def generate_sales_entries(total: float, vat: float, vat_rate: float) -> list[dict]:
    """Generate VAS-correct sales invoice entries (Dr131/Cr511, Dr131/Cr3331)."""
    entries = []

    # Line 1: Revenue - Dr 131 (Receivables) / Cr 511 (Revenue)
    if total > 0:
        entries.append(
            {
                "line_no": 1,
                "debit_account": "131",
                "debit_account_name": "Phải thu khách hàng",
                "credit_account": "511",
                "credit_account_name": "Doanh thu bán hàng",
                "amount": total,
                "currency": "VND",
                "description": "Doanh thu bán hàng",
                "evidence_fields": ["invoice.total", "chart_of_accounts.511", "chart_of_accounts.131"],
            }
        )

    # Line 2: VAT Output - Dr 131 / Cr 3331 (only if VAT > 0)
    if vat > 0:
        entries.append(
            {
                "line_no": 2,
                "debit_account": "131",
                "debit_account_name": "Phải thu khách hàng",
                "credit_account": "3331",
                "credit_account_name": "Thuế GTGT đầu ra",
                "amount": vat,
                "currency": "VND",
                "description": f"Thuế GTGT đầu ra {vat_rate * 100:.0f}%",
                "evidence_fields": ["invoice.vat", "invoice.vat_rate", "chart_of_accounts.3331"],
            }
        )

    return entries


def generate_purchase_entries(total: float, vat: float, vat_rate: float) -> list[dict]:
    """Generate VAS-correct purchase invoice entries (Dr156/Cr331, Dr1331/Cr331)."""
    entries = []

    # Line 1: Inventory/Expense - Dr 156 (Inventory) / Cr 331 (Payables)
    if total > 0:
        entries.append(
            {
                "line_no": 1,
                "debit_account": "156",
                "debit_account_name": "Hàng hóa",
                "credit_account": "331",
                "credit_account_name": "Phải trả người bán",
                "amount": total,
                "currency": "VND",
                "description": "Nhập kho hàng hóa",
                "evidence_fields": ["invoice.total", "chart_of_accounts.156", "chart_of_accounts.331"],
            }
        )

    # Line 2: VAT Input - Dr 1331 / Cr 331 (only if VAT > 0)
    if vat > 0:
        entries.append(
            {
                "line_no": 2,
                "debit_account": "1331",
                "debit_account_name": "Thuế GTGT được khấu trừ",
                "credit_account": "331",
                "credit_account_name": "Phải trả người bán",
                "amount": vat,
                "currency": "VND",
                "description": f"Thuế GTGT đầu vào {vat_rate * 100:.0f}%",
                "evidence_fields": ["invoice.vat", "invoice.vat_rate", "chart_of_accounts.1331"],
            }
        )

    return entries


VENDORS = [
    ("Công ty TNHH ABC", "ABC-001"),
    ("Công ty CP XYZ", "XYZ-002"),
    ("TNHH Thương mại DEF", "DEF-003"),
    ("Công ty TNHH GHI", "GHI-004"),
    ("CTCP Sản xuất JKL", "JKL-005"),
]

CUSTOMERS = [
    ("Khách hàng A", "KH-A01"),
    ("Công ty B", "KH-B02"),
    ("Cửa hàng C", "KH-C03"),
    ("Đại lý D", "KH-D04"),
    ("Siêu thị E", "KH-E05"),
]


class PilotDatasetGenerator:
    """Generates pilot dataset with ground truth expected entries."""

    def __init__(self, tenant_id: str = "pilot-tenant"):
        self.tenant_id = tenant_id
        self.invoice_counter = 0

    def generate_pilot_batch(self) -> list[dict[str, Any]]:
        """Generate exactly 30 invoices with balanced scenarios."""
        scenarios = [
            # Sales scenarios (16 total)
            ("sales", "vat_10", 5),
            ("sales", "vat_0", 3),
            ("sales", "vat_exempt", 2),
            ("sales", "missing_vat", 2),
            ("sales", "rounding_mismatch", 2),
            ("sales", "high_value", 2),
            # Purchase scenarios (14 total)
            ("purchase", "vat_10", 5),
            ("purchase", "vat_0", 3),
            ("purchase", "vat_exempt", 2),
            ("purchase", "missing_total", 2),
            ("purchase", "rounding_mismatch", 2),
        ]

        invoices = []
        for doc_type, vat_scenario, count in scenarios:
            for _ in range(count):
                invoice = self._generate_invoice(doc_type, vat_scenario)
                invoices.append(invoice)

        random.shuffle(invoices)
        return invoices

    def _generate_invoice(self, doc_type: str, vat_scenario: str) -> dict[str, Any]:
        """Generate invoice with ground truth expected_entries."""
        self.invoice_counter += 1

        invoice_id = f"PILOT-{datetime.now().strftime('%Y%m%d')}-{self.invoice_counter:04d}"
        trace_id = str(uuid.uuid4())

        # Random date within last 30 days
        days_ago = random.randint(0, 30)
        invoice_date = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")

        # Determine amounts based on scenario
        total, vat, grand_total, vat_rate = self._calculate_amounts(vat_scenario)

        # Select partner
        if doc_type == "sales":
            partner_name, partner_code = random.choice(CUSTOMERS)
            full_doc_type = "sales_invoice"
            text_header = "HOA DON BAN HANG - SALES INVOICE"
        else:
            partner_name, partner_code = random.choice(VENDORS)
            full_doc_type = "purchase_invoice"
            text_header = "HOA DON MUA HANG - PURCHASE INVOICE"

        # Generate expected entries (ground truth)
        if doc_type == "sales":
            expected_entries = generate_sales_entries(total, vat, vat_rate)
        else:
            expected_entries = generate_purchase_entries(total, vat, vat_rate)

        # Collect evidence_fields_used from all entries
        all_evidence_fields = set()
        for entry in expected_entries:
            all_evidence_fields.update(entry.get("evidence_fields", []))

        # Build OCR-like text
        text = self._build_ocr_text(
            text_header, invoice_id, invoice_date, partner_name, total, vat, grand_total, vat_rate, vat_scenario
        )

        invoice = {
            "invoice_id": invoice_id,
            "tenant_id": self.tenant_id,
            "trace_id": trace_id,
            "text": text,
            "source_file": f"pilot/{invoice_id}.json",
            # Parsed fields
            "invoice_no": invoice_id,
            "date": invoice_date,
            "doc_type": full_doc_type,
            "partner_name": partner_name,
            "partner_code": partner_code,
            "total": total,
            "vat": vat,
            "grand_total": grand_total,
            "vat_rate": vat_rate,
            # Scenario metadata
            "_scenario": f"{doc_type}/{vat_scenario}",
            "_doc_type_short": doc_type,
            "_vat_scenario": vat_scenario,
            # GROUND TRUTH for evaluation
            "_expected_entries": expected_entries,
            "_expected_confidence": 0.9
            if vat_scenario not in ["missing_vat", "missing_total", "rounding_mismatch"]
            else 0.7,
            "_expected_needs_review": vat_scenario in ["missing_vat", "missing_total", "rounding_mismatch"],
            "_expected_evidence_fields_used": sorted(list(all_evidence_fields)),
        }

        return invoice

    def _calculate_amounts(self, vat_scenario: str) -> tuple[float, float, float, float]:
        """Calculate amounts based on VAT scenario."""
        if vat_scenario == "vat_10":
            total = random.randint(5, 50) * 1_000_000  # 5M - 50M
            vat_rate = 0.10
            vat = total * vat_rate
            grand_total = total + vat
        elif vat_scenario == "vat_0" or vat_scenario == "vat_exempt":
            total = random.randint(5, 50) * 1_000_000
            vat_rate = 0.0
            vat = 0
            grand_total = total
        elif vat_scenario == "missing_vat":
            total = random.randint(5, 50) * 1_000_000
            vat_rate = 0.10  # Assume 10% when missing
            vat = 0  # Missing in invoice
            grand_total = total  # Only total shown
        elif vat_scenario == "missing_total":
            vat_rate = 0.10
            grand_total = random.randint(5, 55) * 1_000_000
            total = grand_total / (1 + vat_rate)
            vat = grand_total - total
        elif vat_scenario == "rounding_mismatch":
            total = random.randint(5, 50) * 1_000_000 + 123  # Odd number
            vat_rate = 0.10
            vat = round(total * vat_rate)
            grand_total = total + vat + random.choice([-1, 1])  # Slight mismatch
        elif vat_scenario == "high_value":
            total = random.randint(100, 500) * 1_000_000  # 100M - 500M
            vat_rate = 0.10
            vat = total * vat_rate
            grand_total = total + vat
        else:
            total = random.randint(5, 50) * 1_000_000
            vat_rate = 0.10
            vat = total * vat_rate
            grand_total = total + vat

        return round(total), round(vat), round(grand_total), vat_rate

    def _build_ocr_text(
        self,
        header: str,
        invoice_id: str,
        date: str,
        partner: str,
        total: float,
        vat: float,
        grand_total: float,
        vat_rate: float,
        vat_scenario: str,
    ) -> str:
        """Build OCR-like text for invoice."""
        lines = [
            header,
            f"Invoice No: {invoice_id}",
            f"Date: {date}",
            f"Customer: {partner}" if "SALES" in header else f"Vendor: {partner}",
            "",
            "Items:",
            f"1. Hàng hóa/Dịch vụ - {total:,.0f} VND",
            "",
        ]

        if vat_scenario == "missing_vat":
            lines.append(f"Total: {total:,.0f} VND")
        elif vat_scenario == "missing_total":
            lines.append(f"VAT ({vat_rate * 100:.0f}%): {vat:,.0f} VND")
            lines.append(f"Grand Total: {grand_total:,.0f} VND")
        else:
            lines.append(f"Total: {total:,.0f} VND")
            if vat > 0:
                lines.append(f"VAT ({vat_rate * 100:.0f}%): {vat:,.0f} VND")
            lines.append(f"Grand Total: {grand_total:,.0f} VND")

        return "\n".join(lines)

    def save_pilot_batch(self, output_dir: str = "/root/erp-ai/data/pilot") -> list[str]:
        """Generate and save pilot batch to files."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        invoices = self.generate_pilot_batch()
        saved_files = []

        for invoice in invoices:
            filepath = Path(output_dir) / f"{invoice['invoice_id']}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(invoice, f, ensure_ascii=False, indent=2)
            saved_files.append(str(filepath))

        # Save manifest
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "count": len(invoices),
            "scenarios": {},
            "files": saved_files,
        }
        for inv in invoices:
            scenario = inv["_scenario"]
            manifest["scenarios"][scenario] = manifest["scenarios"].get(scenario, 0) + 1

        manifest_path = Path(output_dir) / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return saved_files


if __name__ == "__main__":
    generator = PilotDatasetGenerator()
    files = generator.save_pilot_batch()
    print(f"Generated {len(files)} pilot invoices")

    # Show scenario distribution
    invoices = generator.generate_pilot_batch()
    scenarios = {}
    for inv in invoices:
        s = inv["_scenario"]
        scenarios[s] = scenarios.get(s, 0) + 1

    print("\nScenario distribution:")
    for s, c in sorted(scenarios.items()):
        print(f"  {s}: {c}")
