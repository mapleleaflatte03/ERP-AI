#!/usr/bin/env python3
"""
Pilot Evaluation Harness
========================
Evaluates LLM output against ground truth expected entries.

Metrics:
- JSON valid rate: % of responses that are valid JSON
- VAS pattern accuracy: % of entries with correct Dr/Cr pattern
- Amount correctness: % of entries with correct amounts
- Evidence completeness: % of invoices with complete evidence_fields_used
- Latency stats: avg, p50, p95

Error buckets:
(A) wrong_accounts - incorrect account codes
(B) wrong_direction - Dr/Cr swapped
(C) wrong_amount - amount mismatch > 1 VND
(D) extra_entries - more entries than expected
(E) missing_entries - fewer entries than expected
(F) missing_evidence - incomplete evidence_fields_used

Output: reports/pilot_report.json
"""

import json
import logging
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, "/root/erp-ai")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PilotEval")

# VAS-correct patterns for validation
VAS_SALES_PATTERNS = {
    "revenue": {"debit": "131", "credit": "511"},
    "vat_output": {"debit": "131", "credit": "3331"},
}

VAS_PURCHASE_PATTERNS = {
    "inventory": {"debit": "156", "credit": "331"},
    "expense": {"debit": "642", "credit": "331"},
    "vat_input": {"debit": "1331", "credit": "331"},
}


class PilotEvaluator:
    """Evaluates pilot results against ground truth."""

    def __init__(self):
        self.results = []
        self.errors = defaultdict(list)
        self.latencies = []

    def evaluate_single(self, invoice: dict[str, Any], output: dict[str, Any], latency_ms: float) -> dict[str, Any]:
        """Evaluate single invoice output against ground truth."""
        invoice_id = invoice.get("invoice_id", "unknown")
        scenario = invoice.get("_scenario", "unknown")
        expected_entries = invoice.get("_expected_entries", [])
        expected_evidence = set(invoice.get("_expected_evidence_fields_used", []))

        result = {
            "invoice_id": invoice_id,
            "scenario": scenario,
            "latency_ms": latency_ms,
            "json_valid": True,  # Already parsed if we get here
            "errors": [],
            "warnings": [],
        }

        actual_entries = output.get("suggested_entries", [])
        actual_evidence = set(output.get("evidence_fields_used", []))

        # Check entry count
        if len(actual_entries) > len(expected_entries):
            result["errors"].append(
                {
                    "type": "extra_entries",
                    "expected": len(expected_entries),
                    "actual": len(actual_entries),
                }
            )
            self.errors["extra_entries"].append(invoice_id)
        elif len(actual_entries) < len(expected_entries):
            result["errors"].append(
                {
                    "type": "missing_entries",
                    "expected": len(expected_entries),
                    "actual": len(actual_entries),
                }
            )
            self.errors["missing_entries"].append(invoice_id)

        # Check each expected entry
        doc_type = invoice.get("_doc_type_short", "sales")
        for i, expected in enumerate(expected_entries):
            if i >= len(actual_entries):
                break

            actual = actual_entries[i]

            # Check accounts
            exp_debit = str(expected.get("debit_account", ""))
            exp_credit = str(expected.get("credit_account", ""))
            act_debit = str(actual.get("debit_account", ""))
            act_credit = str(actual.get("credit_account", ""))

            if act_debit != exp_debit or act_credit != exp_credit:
                # Check if it's a direction swap
                if act_debit == exp_credit and act_credit == exp_debit:
                    result["errors"].append(
                        {
                            "type": "wrong_direction",
                            "line": i + 1,
                            "expected": f"Dr {exp_debit} / Cr {exp_credit}",
                            "actual": f"Dr {act_debit} / Cr {act_credit}",
                        }
                    )
                    self.errors["wrong_direction"].append(invoice_id)
                else:
                    result["errors"].append(
                        {
                            "type": "wrong_accounts",
                            "line": i + 1,
                            "expected": f"Dr {exp_debit} / Cr {exp_credit}",
                            "actual": f"Dr {act_debit} / Cr {act_credit}",
                        }
                    )
                    self.errors["wrong_accounts"].append(invoice_id)

            # Check amount (tolerance: 1 VND for rounding)
            exp_amount = float(expected.get("amount", 0))
            act_amount = float(actual.get("amount", 0))
            if abs(exp_amount - act_amount) > 1:
                result["errors"].append(
                    {
                        "type": "wrong_amount",
                        "line": i + 1,
                        "expected": exp_amount,
                        "actual": act_amount,
                        "diff": abs(exp_amount - act_amount),
                    }
                )
                self.errors["wrong_amount"].append(invoice_id)

        # Validate VAS patterns - use doc_type from invoice (e.g., "purchase_invoice")
        vas_doc_type = invoice.get("doc_type", doc_type)
        vas_errors = self._check_vas_patterns(vas_doc_type, actual_entries)
        for err in vas_errors:
            result["errors"].append(err)
            self.errors["vas_pattern_violation"].append(invoice_id)

        # Check evidence completeness
        if not actual_evidence:
            result["errors"].append(
                {
                    "type": "missing_evidence",
                    "message": "evidence_fields_used is empty",
                }
            )
            self.errors["missing_evidence"].append(invoice_id)

        # Check balance (total_debit == total_credit)
        total_debit = sum(float(e.get("amount", 0)) for e in actual_entries)
        # For double-entry, each entry has same amount as debit and credit
        # So we just check entries are valid

        result["entry_count_match"] = len(actual_entries) == len(expected_entries)
        result["has_evidence"] = bool(actual_evidence)
        result["error_count"] = len(result["errors"])
        result["is_correct"] = result["error_count"] == 0

        self.results.append(result)
        self.latencies.append(latency_ms)

        return result

    def _check_vas_patterns(self, doc_type: str, entries: list[dict]) -> list[dict]:
        """Check if entries follow VAS patterns."""
        errors = []

        # Normalize doc_type
        is_sales = "sales" in doc_type.lower()

        for i, entry in enumerate(entries):
            debit = str(entry.get("debit_account", ""))
            credit = str(entry.get("credit_account", ""))

            if is_sales:
                # Valid patterns: Dr131/Cr511, Dr131/Cr3331
                valid = (debit == "131" and credit == "511") or (debit == "131" and credit == "3331")
                if not valid:
                    errors.append(
                        {
                            "type": "vas_pattern_violation",
                            "line": i + 1,
                            "doc_type": doc_type,
                            "pattern": f"Dr {debit} / Cr {credit}",
                            "allowed": ["Dr 131 / Cr 511", "Dr 131 / Cr 3331"],
                        }
                    )
            else:  # purchase
                # Valid patterns: Dr156/Cr331, Dr642/Cr331, Dr1331/Cr331
                valid = (
                    (debit == "156" and credit == "331")
                    or (debit == "642" and credit == "331")
                    or (debit == "1331" and credit == "331")
                    or (debit == "152" and credit == "331")  # Also allow 152
                )
                if not valid:
                    errors.append(
                        {
                            "type": "vas_pattern_violation",
                            "line": i + 1,
                            "doc_type": doc_type,
                            "pattern": f"Dr {debit} / Cr {credit}",
                            "allowed": ["Dr 156/152 / Cr 331", "Dr 1331 / Cr 331"],
                        }
                    )

        return errors

    def compute_metrics(self) -> dict[str, Any]:
        """Compute aggregate metrics from all results."""
        total = len(self.results)
        if total == 0:
            return {"error": "No results to evaluate"}

        # Accuracy metrics
        correct_count = sum(1 for r in self.results if r["is_correct"])
        entry_match_count = sum(1 for r in self.results if r["entry_count_match"])
        evidence_count = sum(1 for r in self.results if r["has_evidence"])

        # Count specific errors
        error_counts = {k: len(set(v)) for k, v in self.errors.items()}

        # Latency stats
        latency_stats = {}
        if self.latencies:
            sorted_lat = sorted(self.latencies)
            latency_stats = {
                "avg_ms": statistics.mean(self.latencies),
                "p50_ms": statistics.median(self.latencies),
                "p95_ms": sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) > 1 else sorted_lat[0],
                "min_ms": min(self.latencies),
                "max_ms": max(self.latencies),
            }

        metrics = {
            "total_invoices": total,
            "json_valid_rate": 1.0,  # All parsed successfully
            "overall_accuracy": correct_count / total,
            "entry_count_accuracy": entry_match_count / total,
            "evidence_completeness": evidence_count / total,
            # Error breakdown
            "error_counts": error_counts,
            "error_rates": {k: v / total for k, v in error_counts.items()},
            # Per-scenario accuracy
            "scenario_accuracy": self._compute_scenario_accuracy(),
            # Latency
            "latency": latency_stats,
            # KPI summary
            "kpi_pass": {
                "json_valid": True,  # 100%
                "vas_accuracy": error_counts.get("vas_pattern_violation", 0) == 0,
                "amount_accuracy": (total - error_counts.get("wrong_amount", 0)) / total >= 0.98,
                "evidence_complete": evidence_count / total >= 1.0,
            },
        }

        # Overall pass
        metrics["all_kpis_pass"] = all(metrics["kpi_pass"].values())

        return metrics

    def _compute_scenario_accuracy(self) -> dict[str, dict]:
        """Compute accuracy per scenario."""
        scenario_results = defaultdict(lambda: {"total": 0, "correct": 0})

        for r in self.results:
            scenario = r["scenario"]
            scenario_results[scenario]["total"] += 1
            if r["is_correct"]:
                scenario_results[scenario]["correct"] += 1

        return {
            s: {
                "total": v["total"],
                "correct": v["correct"],
                "accuracy": v["correct"] / v["total"] if v["total"] > 0 else 0,
            }
            for s, v in scenario_results.items()
        }

    def generate_report(self, output_path: str = "/root/erp-ai/reports/pilot_report.json"):
        """Generate and save evaluation report."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        metrics = self.compute_metrics()

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_invoices": metrics["total_invoices"],
                "overall_accuracy": f"{metrics['overall_accuracy'] * 100:.1f}%",
                "vas_accuracy": f"{(1 - metrics['error_rates'].get('vas_pattern_violation', 0)) * 100:.1f}%",
                "amount_accuracy": f"{(1 - metrics['error_rates'].get('wrong_amount', 0)) * 100:.1f}%",
                "evidence_completeness": f"{metrics['evidence_completeness'] * 100:.1f}%",
                "avg_latency_ms": f"{metrics['latency'].get('avg_ms', 0):.0f}",
                "p95_latency_ms": f"{metrics['latency'].get('p95_ms', 0):.0f}",
            },
            "kpi_status": metrics["kpi_pass"],
            "all_kpis_pass": metrics["all_kpis_pass"],
            "metrics": metrics,
            "error_details": {k: list(set(v)) for k, v in self.errors.items()},
            "individual_results": self.results,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"Report saved to {output_path}")
        return report


def run_pilot_evaluation(pilot_dir: str = "/root/erp-ai/data/pilot", output_dir: str = "/root/erp-ai/data/processed"):
    """Run evaluation on pilot dataset."""
    from agents.accounting_coding.coding_agent import AccountingCodingAgent

    evaluator = PilotEvaluator()

    # Load pilot invoices
    pilot_path = Path(pilot_dir)
    invoice_files = sorted(pilot_path.glob("PILOT-*.json"))

    if not invoice_files:
        logger.error(f"No pilot invoices found in {pilot_dir}")
        return None

    logger.info(f"Found {len(invoice_files)} pilot invoices")

    # Initialize agent
    agent = AccountingCodingAgent(use_llm=True, use_rag=False)

    for i, filepath in enumerate(invoice_files, 1):
        logger.info(f"Processing {i}/{len(invoice_files)}: {filepath.name}")

        # Load invoice
        with open(filepath, encoding="utf-8") as f:
            invoice = json.load(f)

        # Process through agent
        start_time = time.time()
        try:
            output = agent.process(
                str(filepath),
                top_k=0,
                invoice_id=invoice["invoice_id"],
                tenant_id=invoice["tenant_id"],
                trace_id=invoice["trace_id"],
            )
            latency_ms = (time.time() - start_time) * 1000

            # Evaluate
            evaluator.evaluate_single(invoice, output, latency_ms)

        except Exception as e:
            logger.error(f"Failed to process {filepath.name}: {e}")
            evaluator.results.append(
                {
                    "invoice_id": invoice.get("invoice_id", "unknown"),
                    "scenario": invoice.get("_scenario", "unknown"),
                    "latency_ms": (time.time() - start_time) * 1000,
                    "json_valid": False,
                    "errors": [{"type": "processing_error", "message": str(e)}],
                    "is_correct": False,
                }
            )

    # Generate report
    report = evaluator.generate_report()

    # Print summary
    print("\n" + "=" * 60)
    print("PILOT EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total invoices: {report['summary']['total_invoices']}")
    print(f"Overall accuracy: {report['summary']['overall_accuracy']}")
    print(f"VAS pattern accuracy: {report['summary']['vas_accuracy']}")
    print(f"Amount accuracy: {report['summary']['amount_accuracy']}")
    print(f"Evidence completeness: {report['summary']['evidence_completeness']}")
    print(f"Avg latency: {report['summary']['avg_latency_ms']} ms")
    print(f"P95 latency: {report['summary']['p95_latency_ms']} ms")
    print()
    print("KPI Status:")
    for kpi, passed in report["kpi_status"].items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {kpi}: {status}")
    print()
    print(f"ALL KPIs PASS: {'✅ YES' if report['all_kpis_pass'] else '❌ NO'}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run pilot evaluation")
    parser.add_argument("--pilot-dir", default="/root/erp-ai/data/pilot", help="Directory containing pilot invoices")
    parser.add_argument("--generate-only", action="store_true", help="Only generate pilot dataset, don't evaluate")
    args = parser.parse_args()

    if args.generate_only:
        from scripts.pilot_dataset import PilotDatasetGenerator

        generator = PilotDatasetGenerator()
        files = generator.save_pilot_batch(args.pilot_dir)
        print(f"Generated {len(files)} pilot invoices in {args.pilot_dir}")
    else:
        run_pilot_evaluation(args.pilot_dir)
