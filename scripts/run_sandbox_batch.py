#!/usr/bin/env python3
"""
ERP Sandbox Batch Runner
========================
Generates 200 synthetic invoices (Sales/Purchase, VAT 0%/10%/missing)
and runs them through the full pipeline to produce KPI metrics.

Output:
- reports/batch_metrics.json - KPI summary
- reports/batch_failures.json - Failed invoices with reasons

Usage:
    cd /root/erp-ai
    source venv/bin/activate
    python scripts/run_sandbox_batch.py --count 200
"""

import argparse
import json
import logging
import os
import random
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root
sys.path.insert(0, "/root/erp-ai")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/root/erp-ai/logs/sandbox_batch.log")],
)
logger = logging.getLogger("SandboxBatch")

# ============================================================================
# INVOICE GENERATOR
# ============================================================================

VENDORS = [
    ("Công ty TNHH ABC", "ABC-001"),
    ("Công ty CP XYZ", "XYZ-002"),
    ("Công ty Thương mại Hà Nội", "HN-003"),
    ("Công ty TNHH Đầu tư Sài Gòn", "SG-004"),
    ("Công ty CP Công nghệ Việt Nam", "VN-005"),
]

CUSTOMERS = [
    ("Công ty TNHH Khách hàng A", "KH-A001"),
    ("Công ty CP Khách hàng B", "KH-B002"),
    ("Doanh nghiệp tư nhân C", "KH-C003"),
    ("Hộ kinh doanh D", "KH-D004"),
    ("Công ty TNHH Khách hàng E", "KH-E005"),
]

PRODUCTS_SALES = [
    ("Laptop Dell XPS 15", 25000000),
    ("Màn hình Samsung 27 inch", 8500000),
    ("Bàn phím cơ Logitech", 2500000),
    ("Chuột không dây", 850000),
    ("Tai nghe Bluetooth", 1200000),
    ("Ổ cứng SSD 1TB", 3500000),
    ("RAM 16GB DDR4", 1800000),
    ("Card đồ họa RTX 3060", 12000000),
    ("Webcam Logitech C920", 2200000),
    ("Dịch vụ tư vấn IT", 15000000),
    ("Phần mềm ERP License", 50000000),
    ("Dịch vụ bảo trì hệ thống", 8000000),
]

PRODUCTS_PURCHASE = [
    ("Nguyên liệu thô A", 5000000),
    ("Linh kiện điện tử B", 3000000),
    ("Vật tư văn phòng", 500000),
    ("Thiết bị máy tính", 15000000),
    ("Dịch vụ vận chuyển", 2000000),
    ("Tiền thuê kho bãi", 10000000),
    ("Nguyên liệu đầu vào C", 8000000),
    ("Phụ tùng máy móc", 6000000),
]


class InvoiceGenerator:
    """Generates synthetic ERP invoices with various scenarios."""

    def __init__(self, tenant_id: str = "sandbox-tenant"):
        self.tenant_id = tenant_id
        self.invoice_counter = 0

    def generate_batch(self, count: int) -> list[dict[str, Any]]:
        """Generate a batch of invoices with realistic distribution."""
        invoices = []

        # Distribution: 60% sales, 40% purchase
        # VAT: 70% VAT 10%, 15% VAT 0%, 10% VAT exempt, 5% missing/ambiguous
        scenarios = []

        # Sales scenarios
        sales_count = int(count * 0.6)
        scenarios.extend([("sales", "vat_10")] * int(sales_count * 0.70))
        scenarios.extend([("sales", "vat_0")] * int(sales_count * 0.15))
        scenarios.extend([("sales", "vat_exempt")] * int(sales_count * 0.10))
        scenarios.extend([("sales", "missing_vat")] * int(sales_count * 0.05))

        # Purchase scenarios
        purchase_count = count - sales_count
        scenarios.extend([("purchase", "vat_10")] * int(purchase_count * 0.70))
        scenarios.extend([("purchase", "vat_0")] * int(purchase_count * 0.15))
        scenarios.extend([("purchase", "vat_exempt")] * int(purchase_count * 0.10))
        scenarios.extend([("purchase", "missing_vat")] * int(purchase_count * 0.05))

        # Add edge cases
        edge_cases = [
            ("sales", "rounding_mismatch"),
            ("purchase", "rounding_mismatch"),
            ("sales", "missing_total"),
            ("purchase", "missing_total"),
            ("sales", "high_value"),
            ("purchase", "high_value"),
        ]
        scenarios.extend(edge_cases * max(1, count // 50))

        # Shuffle and limit to count
        random.shuffle(scenarios)
        scenarios = scenarios[:count]

        for doc_type, vat_scenario in scenarios:
            invoice = self._generate_invoice(doc_type, vat_scenario)
            invoices.append(invoice)

        return invoices

    def _generate_invoice(self, doc_type: str, vat_scenario: str) -> dict[str, Any]:
        """Generate a single invoice based on scenario."""
        self.invoice_counter += 1

        # Basic info
        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{self.invoice_counter:04d}"
        trace_id = str(uuid.uuid4())

        # Random date within last 30 days
        days_ago = random.randint(0, 30)
        invoice_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        # Select products and calculate amounts
        if doc_type == "sales":
            products = random.sample(PRODUCTS_SALES, k=random.randint(1, 4))
            customer = random.choice(CUSTOMERS)
            partner_name = customer[0]
            partner_code = customer[1]
        else:
            products = random.sample(PRODUCTS_PURCHASE, k=random.randint(1, 3))
            vendor = random.choice(VENDORS)
            partner_name = vendor[0]
            partner_code = vendor[1]

        # Calculate line items
        items = []
        net_amount = 0
        for i, (name, base_price) in enumerate(products, start=1):
            qty = random.randint(1, 5)
            unit_price = base_price * random.uniform(0.9, 1.1)  # +/- 10% variation
            line_total = round(qty * unit_price)
            net_amount += line_total
            items.append(
                {
                    "line_no": i,
                    "description": name,
                    "quantity": qty,
                    "unit_price": round(unit_price),
                    "amount": line_total,
                }
            )

        # Determine VAT
        vat_rate = 0.1
        vat_amount = 0
        total_amount = net_amount
        needs_human_review = False
        expected_risks = []

        if vat_scenario == "vat_10":
            vat_rate = 0.1
            vat_amount = round(net_amount * vat_rate)
            total_amount = net_amount + vat_amount

        elif vat_scenario == "vat_0":
            vat_rate = 0.0
            vat_amount = 0
            total_amount = net_amount

        elif vat_scenario == "vat_exempt":
            vat_rate = None  # Exempt
            vat_amount = None
            total_amount = net_amount
            expected_risks.append("VAT exempt invoice")

        elif vat_scenario == "missing_vat":
            vat_rate = None
            vat_amount = None
            total_amount = net_amount
            needs_human_review = True
            expected_risks.append("VAT information missing")

        elif vat_scenario == "rounding_mismatch":
            vat_rate = 0.1
            vat_amount = round(net_amount * vat_rate) + random.choice([-1, 1, -2, 2])  # Off by 1-2
            total_amount = net_amount + vat_amount
            needs_human_review = True
            expected_risks.append("Total mismatch (rounding)")

        elif vat_scenario == "missing_total":
            vat_rate = 0.1
            vat_amount = round(net_amount * vat_rate)
            total_amount = None  # Missing
            needs_human_review = True
            expected_risks.append("Total amount missing")

        elif vat_scenario == "high_value":
            # Multiply amounts for high-value test
            multiplier = random.randint(10, 50)
            net_amount = net_amount * multiplier
            vat_rate = 0.1
            vat_amount = round(net_amount * vat_rate)
            total_amount = net_amount + vat_amount
            for item in items:
                item["amount"] = item["amount"] * multiplier
                item["unit_price"] = item["unit_price"] * multiplier

        # Build invoice
        invoice = {
            "invoice_id": invoice_id,
            "tenant_id": self.tenant_id,
            "trace_id": trace_id,
            "invoice_no": invoice_id,
            "date": invoice_date,
            "doc_type": f"{doc_type}_invoice",
            "partner_name": partner_name,
            "partner_code": partner_code,
            "items": items,
            "net_amount": net_amount,
            "vat_rate": vat_rate,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "total": net_amount,  # Alias for compatibility
            "vat": vat_amount,
            "grand_total": total_amount,
            "currency": "VND",
            "total_amount_includes_vat": False,
            # Metadata for evaluation
            "_scenario": f"{doc_type}/{vat_scenario}",
            "_expected_review": needs_human_review,
            "_expected_risks": expected_risks,
        }

        # Expected accounts for validation
        if doc_type == "sales":
            invoice["_expected_accounts"] = {
                "debit": ["131"],
                "credit": ["511", "3331"] if vat_amount and vat_amount > 0 else ["511"],
            }
        else:
            invoice["_expected_accounts"] = {
                "debit": ["156", "642", "1331"] if vat_amount and vat_amount > 0 else ["156", "642"],
                "credit": ["331"],
            }

        return invoice


# ============================================================================
# BATCH PROCESSOR
# ============================================================================


class BatchProcessor:
    """Processes invoices through the coding agent and collects metrics."""

    def __init__(self, use_do_agent: bool = True):
        self.use_do_agent = use_do_agent
        self.results = []
        self.failures = []

    def process_batch(self, invoices: list[dict[str, Any]]) -> dict[str, Any]:
        """Process all invoices and return metrics."""
        from agents.accounting_coding.coding_agent import AccountingCodingAgent

        # Initialize agent (skip RAG for batch processing speed)
        logger.info(f"Initializing agent (DO Agent: {self.use_do_agent})")
        agent = AccountingCodingAgent(use_llm=True, use_rag=False)

        total = len(invoices)
        logger.info(f"Processing {total} invoices...")

        for i, invoice in enumerate(invoices, start=1):
            if i % 10 == 0 or i == total:
                logger.info(f"Progress: {i}/{total} ({i * 100 // total}%)")

            try:
                result = self._process_single(agent, invoice)
                self.results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {invoice.get('invoice_id')}: {e}")
                self.failures.append(
                    {
                        "invoice_id": invoice.get("invoice_id"),
                        "trace_id": invoice.get("trace_id"),
                        "scenario": invoice.get("_scenario"),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )

        return self._compute_metrics()

    def _process_single(self, agent, invoice: dict[str, Any]) -> dict[str, Any]:
        """Process a single invoice and evaluate result."""
        # Save invoice to temp file (agent expects file path)
        temp_dir = Path("/root/erp-ai/data/sandbox_temp")
        temp_dir.mkdir(exist_ok=True)

        temp_file = temp_dir / f"{invoice['invoice_id']}.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            # Format as OCR-like output
            ocr_data = {
                "text": self._format_ocr_text(invoice),
                "source_file": str(temp_file),
                "invoice_data": invoice,
            }
            json.dump(ocr_data, f, ensure_ascii=False, indent=2)

        try:
            # Process through agent
            result = agent.process(
                str(temp_file),
                top_k=0,  # No RAG
                invoice_id=invoice["invoice_id"],
                tenant_id=invoice["tenant_id"],
                trace_id=invoice["trace_id"],
            )

            # Evaluate result
            evaluation = self._evaluate_result(invoice, result)

            return {
                "invoice_id": invoice["invoice_id"],
                "scenario": invoice.get("_scenario"),
                "confidence": result.get("confidence", 0),
                "llm_used": result.get("llm_used", False),
                "llm_model": result.get("model", "unknown"),
                "needs_human_review": result.get("needs_human_review", False),
                "entry_count": len(result.get("suggested_entries", [])),
                "risks": result.get("risks", []),
                "evidence_fields_used": result.get("evidence_fields_used", []),
                "evaluation": evaluation,
            }
        finally:
            # Cleanup
            if temp_file.exists():
                temp_file.unlink()

    def _format_ocr_text(self, invoice: dict[str, Any]) -> str:
        """Format invoice as OCR-like text."""
        doc_type_vn = "HOA DON BAN HANG" if "sales" in invoice.get("doc_type", "") else "HOA DON MUA HANG"

        lines = [
            f"{doc_type_vn}",
            f"Invoice No: {invoice.get('invoice_no', 'N/A')}",
            f"Date: {invoice.get('date', 'N/A')}",
            f"Partner: {invoice.get('partner_name', 'N/A')}",
            "",
        ]

        for item in invoice.get("items", []):
            lines.append(f"{item['line_no']}. {item['description']} - {item['amount']:,.0f} VND")

        lines.extend(
            [
                "",
                f"Total: {invoice.get('net_amount', 0):,.0f} VND",
            ]
        )

        if invoice.get("vat_amount") is not None:
            vat_rate = invoice.get("vat_rate", 0.1)
            if vat_rate is not None:
                lines.append(f"VAT ({vat_rate * 100:.0f}%): {invoice.get('vat_amount', 0):,.0f} VND")
            else:
                lines.append(f"VAT: {invoice.get('vat_amount', 0):,.0f} VND")

        if invoice.get("total_amount") is not None:
            lines.append(f"Grand Total: {invoice.get('total_amount', 0):,.0f} VND")

        return "\n".join(lines)

    def _evaluate_result(self, invoice: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        """Evaluate proposal accuracy against expected values."""
        evaluation = {
            "account_correct": False,
            "amount_correct": False,
            "vat_correct": False,
            "review_correct": False,
            "issues": [],
        }

        entries = result.get("suggested_entries", [])
        expected = invoice.get("_expected_accounts", {})

        # Check accounts
        actual_debits = set()
        actual_credits = set()
        total_amount = 0
        vat_entry_amount = 0

        for entry in entries:
            debit = entry.get("debit_account", "")
            credit = entry.get("credit_account", "")
            amount = entry.get("amount", 0)

            actual_debits.add(debit)
            actual_credits.add(credit)
            total_amount += amount

            # Track VAT entry
            if credit in ["3331"] or debit in ["1331"]:
                vat_entry_amount = amount

        expected_debits = set(expected.get("debit", []))
        expected_credits = set(expected.get("credit", []))

        # Account accuracy: at least one correct debit AND one correct credit
        debit_match = bool(actual_debits.intersection(expected_debits))
        credit_match = bool(actual_credits.intersection(expected_credits))
        evaluation["account_correct"] = debit_match and credit_match

        if not debit_match:
            evaluation["issues"].append(f"Debit mismatch: expected {expected_debits}, got {actual_debits}")
        if not credit_match:
            evaluation["issues"].append(f"Credit mismatch: expected {expected_credits}, got {actual_credits}")

        # Amount accuracy (within 1% tolerance)
        # BUG FIX: Compute expected_total from net_amount + vat_amount if total_amount is None
        expected_total = invoice.get("total_amount") or invoice.get("grand_total")
        if expected_total is None:
            # Fallback: compute from net + vat
            net = invoice.get("net_amount", 0) or 0
            vat_amt = invoice.get("vat_amount", 0) or 0
            if net > 0 or vat_amt > 0:
                expected_total = net + vat_amt

        if expected_total and expected_total > 0:
            tolerance = expected_total * 0.01
            if abs(total_amount - expected_total) <= tolerance:
                evaluation["amount_correct"] = True
            else:
                evaluation["issues"].append(f"Amount mismatch: expected {expected_total:,.0f}, got {total_amount:,.0f}")
        else:
            evaluation["amount_correct"] = len(entries) > 0  # At least generated something

        # VAT correctness
        expected_vat = invoice.get("vat_amount")
        if expected_vat is not None and expected_vat > 0:
            vat_tolerance = expected_vat * 0.02  # 2% tolerance for rounding
            if abs(vat_entry_amount - expected_vat) <= vat_tolerance:
                evaluation["vat_correct"] = True
            else:
                evaluation["issues"].append(f"VAT mismatch: expected {expected_vat:,.0f}, got {vat_entry_amount:,.0f}")
        elif expected_vat == 0 or expected_vat is None:
            # No VAT expected
            evaluation["vat_correct"] = vat_entry_amount == 0 or invoice.get("vat_rate") == 0

        # Review flag correctness
        expected_review = invoice.get("_expected_review", False)
        actual_review = result.get("needs_human_review", False)
        evaluation["review_correct"] = (expected_review == actual_review) or actual_review  # Being conservative is OK

        return evaluation

    def _compute_metrics(self) -> dict[str, Any]:
        """Compute KPI metrics from all results."""
        total = len(self.results)
        if total == 0:
            return {"error": "No results to analyze"}

        # Basic counts
        auto_postable = sum(1 for r in self.results if not r["needs_human_review"] and r["confidence"] >= 0.8)
        needs_review = sum(1 for r in self.results if r["needs_human_review"])
        llm_used = sum(1 for r in self.results if r["llm_used"])

        # Confidence distribution
        confidences = [r["confidence"] for r in self.results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Evaluation metrics
        account_correct = sum(1 for r in self.results if r["evaluation"]["account_correct"])
        amount_correct = sum(1 for r in self.results if r["evaluation"]["amount_correct"])
        vat_correct = sum(1 for r in self.results if r["evaluation"]["vat_correct"])

        # Scenario breakdown
        scenario_counts = Counter(r["scenario"] for r in self.results)
        scenario_accuracy = {}
        for scenario in scenario_counts:
            scenario_results = [r for r in self.results if r["scenario"] == scenario]
            correct = sum(1 for r in scenario_results if r["evaluation"]["account_correct"])
            scenario_accuracy[scenario] = {
                "count": len(scenario_results),
                "account_accuracy": correct / len(scenario_results) if scenario_results else 0,
            }

        # Risk frequency
        all_risks = []
        for r in self.results:
            all_risks.extend(r.get("risks", []))
        risk_frequency = dict(Counter(all_risks).most_common(10))

        # Model distribution
        model_counts = Counter(r.get("llm_model", "unknown") for r in self.results)

        # Evidence usage
        evidence_used = sum(1 for r in self.results if r.get("evidence_fields_used"))

        metrics = {
            "summary": {
                "total_invoices": total,
                "total_failures": len(self.failures),
                "auto_postable": auto_postable,
                "auto_post_rate": auto_postable / total,
                "needs_human_review": needs_review,
                "needs_review_rate": needs_review / total,
                "llm_used_count": llm_used,
                "llm_used_rate": llm_used / total,
            },
            "confidence": {
                "average": avg_confidence,
                "min": min(confidences) if confidences else 0,
                "max": max(confidences) if confidences else 0,
                "above_80": sum(1 for c in confidences if c >= 0.8) / total,
                "above_90": sum(1 for c in confidences if c >= 0.9) / total,
            },
            "accuracy": {
                "account_accuracy": account_correct / total,
                "amount_accuracy": amount_correct / total,
                "vat_accuracy": vat_correct / total,
                "overall_accuracy": (account_correct + amount_correct + vat_correct) / (total * 3),
            },
            "by_scenario": scenario_accuracy,
            "risks": {
                "top_risks": risk_frequency,
                "total_risk_count": len(all_risks),
            },
            "model_distribution": dict(model_counts),
            "evidence": {
                "invoices_with_evidence": evidence_used,
                "evidence_rate": evidence_used / total,
            },
            "generated_at": datetime.now().isoformat(),
            "batch_id": str(uuid.uuid4())[:8],
        }

        return metrics


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="ERP Sandbox Batch Runner")
    parser.add_argument("--count", type=int, default=200, help="Number of invoices to generate")
    parser.add_argument("--tenant", default="sandbox-tenant", help="Tenant ID")
    parser.add_argument("--output-dir", default="/root/erp-ai/reports", help="Output directory")
    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("ERP SANDBOX BATCH RUNNER")
    logger.info("=" * 60)
    logger.info(f"Count: {args.count}")
    logger.info(f"Tenant: {args.tenant}")
    logger.info(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'local')}")
    if os.getenv("LLM_PROVIDER") == "do_agent":
        logger.info(f"DO Agent URL: {os.getenv('DO_AGENT_URL', 'N/A')[:40]}...")
        logger.info(f"DO Agent Model: {os.getenv('DO_AGENT_MODEL', 'qwen3-32b')}")

    # Generate invoices
    logger.info("\n[1/3] Generating synthetic invoices...")
    generator = InvoiceGenerator(tenant_id=args.tenant)
    invoices = generator.generate_batch(args.count)
    logger.info(f"Generated {len(invoices)} invoices")

    # Show distribution
    scenarios = Counter(inv["_scenario"] for inv in invoices)
    logger.info("Scenario distribution:")
    for scenario, count in sorted(scenarios.items()):
        logger.info(f"  {scenario}: {count}")

    # Process batch
    logger.info("\n[2/3] Processing invoices through pipeline...")
    processor = BatchProcessor(use_do_agent=os.getenv("LLM_PROVIDER") == "do_agent")
    metrics = processor.process_batch(invoices)

    # Save results
    logger.info("\n[3/3] Saving reports...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save metrics
    metrics_file = output_dir / f"batch_metrics_{timestamp}.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info(f"Metrics saved: {metrics_file}")

    # Also save as latest
    latest_metrics = output_dir / "batch_metrics.json"
    with open(latest_metrics, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # Save failures
    if processor.failures:
        failures_file = output_dir / f"batch_failures_{timestamp}.json"
        with open(failures_file, "w", encoding="utf-8") as f:
            json.dump(processor.failures, f, ensure_ascii=False, indent=2)
        logger.info(f"Failures saved: {failures_file}")

        latest_failures = output_dir / "batch_failures.json"
        with open(latest_failures, "w", encoding="utf-8") as f:
            json.dump(processor.failures, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print("\n📊 SUMMARY")
    print(f"  Total Invoices: {metrics['summary']['total_invoices']}")
    print(f"  Failures: {metrics['summary']['total_failures']}")
    print(f"  Auto-Postable: {metrics['summary']['auto_postable']} ({metrics['summary']['auto_post_rate']:.1%})")
    print(f"  Needs Review: {metrics['summary']['needs_human_review']} ({metrics['summary']['needs_review_rate']:.1%})")

    print("\n📈 CONFIDENCE")
    print(f"  Average: {metrics['confidence']['average']:.2%}")
    print(f"  ≥80%: {metrics['confidence']['above_80']:.1%}")
    print(f"  ≥90%: {metrics['confidence']['above_90']:.1%}")

    print("\n✅ ACCURACY")
    print(f"  Account Accuracy: {metrics['accuracy']['account_accuracy']:.1%}")
    print(f"  Amount Accuracy: {metrics['accuracy']['amount_accuracy']:.1%}")
    print(f"  VAT Accuracy: {metrics['accuracy']['vat_accuracy']:.1%}")
    print(f"  Overall: {metrics['accuracy']['overall_accuracy']:.1%}")

    print("\n🤖 MODEL USAGE")
    for model, count in metrics["model_distribution"].items():
        print(f"  {model}: {count}")

    print("\n⚠️ TOP RISKS")
    for risk, count in list(metrics["risks"]["top_risks"].items())[:5]:
        print(f"  {risk}: {count}")

    print("\n📁 OUTPUTS")
    print(f"  {latest_metrics}")
    if processor.failures:
        print(f"  {output_dir / 'batch_failures.json'}")

    print("=" * 60)

    return metrics


if __name__ == "__main__":
    main()
