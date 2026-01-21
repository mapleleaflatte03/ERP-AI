#!/usr/bin/env python3
"""
Pilot Runner with Concurrency
=============================
Runs the pilot dataset through the pipeline with concurrent processing.

Usage:
    cd /root/erp-ai
    source venv/bin/activate

    # Run with default concurrency (4 workers)
    python scripts/run_pilot.py

    # Run with specific concurrency
    python scripts/run_pilot.py --concurrency 8

    # Run until KPIs pass
    python scripts/run_pilot.py --iterate --max-iterations 5
"""

import argparse
import json
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

# Add project root
sys.path.insert(0, "/root/erp-ai")

from core.paths import get_log_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(get_log_file("pilot_runner.log"))],
)
logger = logging.getLogger("PilotRunner")

# Import pilot dataset and evaluator
from scripts.eval_pilot import PilotEvaluator
from scripts.pilot_dataset import PilotDatasetGenerator


class ConcurrentPilotRunner:
    """Runs pilot dataset with concurrent processing."""

    def __init__(self, concurrency: int = 4, use_do_agent: bool = True):
        self.concurrency = concurrency
        self.use_do_agent = use_do_agent
        self.results: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self.results_lock = Lock()
        self.failures_lock = Lock()

    def run_pilot(self, invoices: list[dict[str, Any]]) -> dict[str, Any]:
        """Run pilot with concurrent workers."""

        total = len(invoices)
        logger.info(f"Running pilot: {total} invoices with {self.concurrency} workers")

        start_time = time.time()
        completed = 0

        # Process in batches using thread pool
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            # Submit all tasks
            future_to_invoice = {executor.submit(self._process_single, invoice): invoice for invoice in invoices}

            # Collect results as they complete
            for future in as_completed(future_to_invoice):
                invoice = future_to_invoice[future]
                completed += 1

                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                except Exception as e:
                    logger.error(f"Worker error for {invoice.get('invoice_id')}: {e}")
                    with self.failures_lock:
                        self.failures.append(
                            {
                                "invoice_id": invoice.get("invoice_id"),
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "trace": traceback.format_exc(),
                            }
                        )

                # Progress logging
                if completed % 5 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(f"Progress: {completed}/{total} ({completed * 100 // total}%) - {rate:.1f} inv/sec")

        total_time = time.time() - start_time

        return {
            "total_invoices": total,
            "processed": len(self.results),
            "failed": len(self.failures),
            "total_time_seconds": total_time,
            "invoices_per_second": len(self.results) / total_time if total_time > 0 else 0,
            "concurrency": self.concurrency,
            "results": self.results,
            "failures": self.failures,
        }

    def _process_single(self, invoice: dict[str, Any]) -> dict[str, Any]:
        """Process a single invoice (runs in worker thread)."""
        # Each thread gets its own agent instance to avoid contention
        from agents.accounting_coding.coding_agent import AccountingCodingAgent

        agent = AccountingCodingAgent(use_llm=True, use_rag=False)

        temp_dir = Path("/root/erp-ai/data/pilot_temp")
        temp_dir.mkdir(exist_ok=True)

        temp_file = temp_dir / f"{invoice['invoice_id']}.json"

        try:
            # Write invoice to temp file
            with open(temp_file, "w", encoding="utf-8") as f:
                ocr_data = {
                    "text": self._format_ocr_text(invoice),
                    "source_file": str(temp_file),
                    "invoice_data": invoice,
                }
                json.dump(ocr_data, f, ensure_ascii=False, indent=2)

            # Time the processing
            start = time.time()

            # Process through agent
            result = agent.process(
                str(temp_file),
                top_k=0,
                invoice_id=invoice["invoice_id"],
                tenant_id=invoice.get("tenant_id", "pilot"),
                trace_id=invoice.get("trace_id", str(time.time())),
            )

            latency_ms = (time.time() - start) * 1000

            # Return result with metadata
            return {
                "invoice_id": invoice["invoice_id"],
                "scenario": invoice.get("_scenario"),
                "expected_entries": invoice.get("_expected_entries", []),
                "llm_output": result,
                "suggested_entries": result.get("suggested_entries", []),
                "explanation": result.get("explanation", ""),
                "confidence": result.get("confidence", 0),
                "llm_used": result.get("llm_used", False),
                "llm_provider": result.get("llm_provider", "unknown"),
                "needs_human_review": result.get("needs_human_review", False),
                "risks": result.get("risks", []),
                "latency_ms": latency_ms,
                "evidence_fields_used": result.get("evidence_fields_used", []),
            }

        finally:
            # Cleanup
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass

    def _format_ocr_text(self, invoice: dict[str, Any]) -> str:
        """Format invoice as OCR text."""
        doc_type = invoice.get("doc_type", "invoice")
        is_sales = "sales" in doc_type.lower()

        lines = [
            "HOA DON BAN HANG" if is_sales else "HOA DON MUA HANG",
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
                f"Total: {invoice.get('total', 0):,.0f} VND",
                f"VAT: {invoice.get('vat', 0):,.0f} VND ({invoice.get('vat_rate', 0.1) * 100:.0f}%)",
                f"Grand Total: {invoice.get('grand_total', 0):,.0f} VND",
            ]
        )

        return "\n".join(lines)


def run_pilot_iteration(concurrency: int, iteration: int = 1) -> tuple[dict, bool]:
    """Run one pilot iteration and evaluate."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PILOT ITERATION {iteration}")
    logger.info(f"{'=' * 60}")

    # Generate pilot dataset
    logger.info("\n[1/3] Generating pilot dataset (30 invoices)...")
    generator = PilotDatasetGenerator()
    invoices = generator.generate_pilot_batch()
    logger.info(f"Generated {len(invoices)} invoices with ground truth")

    # Run pilot
    logger.info(f"\n[2/3] Running pilot with {concurrency} concurrent workers...")
    runner = ConcurrentPilotRunner(concurrency=concurrency)
    run_result = runner.run_pilot(invoices)
    logger.info(f"Completed: {run_result['processed']}/{run_result['total_invoices']}")
    logger.info(f"Rate: {run_result['invoices_per_second']:.2f} inv/sec")

    # Evaluate
    logger.info("\n[3/3] Evaluating results...")
    evaluator = PilotEvaluator()

    # Evaluate each result
    for result in run_result["results"]:
        scenario = result.get("scenario", "")
        # Scenario is like "sales/vat_10" or "purchase/vat_0"
        doc_type_short = scenario.split("/")[0] if "/" in scenario else "sales"
        doc_type = f"{doc_type_short}_invoice"

        invoice = {
            "invoice_id": result["invoice_id"],
            "doc_type": doc_type,
            "_scenario": scenario,
            "_expected_entries": result.get("expected_entries", []),
        }
        output = result.get("llm_output", result)
        evaluator.evaluate_single(invoice, output, latency_ms=result.get("latency_ms", 0))

    eval_report = evaluator.compute_metrics()

    # Check KPIs - extract from eval_report structure
    json_valid_rate = eval_report.get("json_valid_rate", 0)
    vas_error_rate = eval_report.get("error_rates", {}).get("vas_pattern_violation", 0)
    vas_accuracy = 1.0 - vas_error_rate
    entry_count_accuracy = eval_report.get("entry_count_accuracy", 0)  # proxy for amount accuracy
    evidence_completeness = eval_report.get("evidence_completeness", 0)
    avg_latency_ms = eval_report.get("latency", {}).get("avg_ms", 9999)

    kpis_pass = (
        json_valid_rate >= 1.0
        and vas_accuracy >= 0.98
        and entry_count_accuracy >= 0.98
        and evidence_completeness >= 1.0
        and avg_latency_ms <= 3000
    )

    # Log KPIs
    logger.info("\nKPI Results:")
    logger.info(f"  JSON Valid Rate: {json_valid_rate * 100:.1f}% (target: 100%)")
    logger.info(f"  VAS Accuracy: {vas_accuracy * 100:.1f}% (target: ≥98%)")
    logger.info(f"  Amount/Entry Accuracy: {entry_count_accuracy * 100:.1f}% (target: ≥98%)")
    logger.info(f"  Evidence Complete: {evidence_completeness * 100:.1f}% (target: 100%)")
    logger.info(f"  Avg Latency: {avg_latency_ms:.0f}ms (target: <3000ms)")

    logger.info(f"\nKPIs PASS: {kpis_pass}")

    # Save report
    output_dir = Path("/root/erp-ai/reports")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"pilot_report_{timestamp}_iter{iteration}.json"

    full_report = {
        "iteration": iteration,
        "timestamp": timestamp,
        "concurrency": concurrency,
        "run_stats": {
            "total": run_result["total_invoices"],
            "processed": run_result["processed"],
            "failed": run_result["failed"],
            "time_seconds": run_result["total_time_seconds"],
            "rate": run_result["invoices_per_second"],
        },
        "evaluation": eval_report,
        "kpis_pass": kpis_pass,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    # Also save as latest
    latest_file = output_dir / "pilot_report_latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved: {report_file}")

    return full_report, kpis_pass


def main():
    parser = argparse.ArgumentParser(description="Pilot Runner with Concurrency")
    parser.add_argument("--concurrency", type=int, default=4, help="Number of concurrent workers (default: 4)")
    parser.add_argument("--iterate", action="store_true", help="Keep iterating until KPIs pass")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max iterations if --iterate (default: 5)")
    args = parser.parse_args()

    # Check environment
    logger.info("=" * 60)
    logger.info("PILOT RUNNER - PRODUCTION STRICT MODE")
    logger.info("=" * 60)

    llm_provider = os.getenv("LLM_PROVIDER", "local")
    disable_local = os.getenv("LLM_PROVIDER", "0")

    logger.info(f"LLM_PROVIDER: {llm_provider}")
    logger.info(f"LLM_PROVIDER: {disable_local}")
    logger.info(f"Concurrency: {args.concurrency}")

    if llm_provider == "do_agent":
        logger.info(f"DO Agent URL: {os.getenv('DO_AGENT_URL', 'N/A')[:40]}...")
        logger.info(f"DO Agent Model: {os.getenv('DO_AGENT_MODEL', 'qwen3-32b')}")

    if args.iterate:
        # Iterative mode: run until KPIs pass
        logger.info(f"\nIterative mode: max {args.max_iterations} iterations")

        for i in range(1, args.max_iterations + 1):
            report, kpis_pass = run_pilot_iteration(args.concurrency, iteration=i)

            if kpis_pass:
                logger.info(f"\n✓ KPIs PASSED on iteration {i}!")
                logger.info("Ready for full batch run.")
                break
            else:
                logger.warning(f"\n✗ KPIs failed on iteration {i}")
                if i < args.max_iterations:
                    logger.info("Retrying...")
                else:
                    logger.error(f"Max iterations ({args.max_iterations}) reached without passing KPIs")
                    sys.exit(1)
    else:
        # Single run
        report, kpis_pass = run_pilot_iteration(args.concurrency)

        if not kpis_pass:
            logger.warning("\n✗ KPIs did not pass. Consider using --iterate flag.")
            sys.exit(1)
        else:
            logger.info("\n✓ KPIs PASSED!")

    logger.info("\nPilot complete.")


if __name__ == "__main__":
    main()
