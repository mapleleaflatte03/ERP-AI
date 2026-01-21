#!/usr/bin/env python3
"""
ASOFT-T Batch Processor for ERPX AI
====================================
Processes multiple invoice JSONs through ASOFT-T Copilot.

Usage:
    cd /root/erp-ai
    source venv/bin/activate
    python scripts/asof_batch_process.py data/processed/pilot_run_*/
    python scripts/asof_batch_process.py data/processed/pilot_run_*/ --bank-txns data/paysim_sample.csv
"""

import csv
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

# Add project root
sys.path.insert(0, "/root/erp-ai")

from agents.accounting_coding.erpx_copilot import ERPXAccountingCopilot

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ASOFBatch")


class ASOFTBatchProcessor:
    """Batch processor for ASOFT-T Copilot."""

    def __init__(self, concurrency: int = 4, strict_mode: bool = False):
        self.concurrency = concurrency
        self.strict_mode = strict_mode
        self.results: list[dict[str, Any]] = []
        self.results_lock = Lock()

    def load_bank_transactions(self, path: str) -> list[dict[str, Any]]:
        """Load bank transactions from JSON or CSV."""
        path = Path(path)

        if path.suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        elif path.suffix == ".csv":
            transactions = []
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle PaySim format
                    txn = {
                        "id": row.get("nameOrig") or row.get("id"),
                        "amount": float(row.get("amount", 0)),
                        "type": row.get("type"),
                        "date": row.get("date"),
                        "memo": row.get("nameDest") or row.get("memo", ""),
                    }
                    transactions.append(txn)
            return transactions

        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def find_invoice_files(self, input_path: str) -> list[Path]:
        """Find all invoice JSON files in input path."""
        input_path = Path(input_path)

        if input_path.is_file():
            return [input_path]

        # Find .json files in the directory (not recursive by default)
        # Exclude: summary files, ocr_results subdirectory
        files = []
        for p in input_path.glob("*.json"):
            name_lower = p.name.lower()
            # Skip summary files
            if "summary" in name_lower:
                continue
            # Skip files that don't look like invoice files
            if not any(prefix in name_lower for prefix in ["sroie_", "vn_", "invoice", "doc"]):
                # Also accept generic numbered files if they have invoice_data
                if not p.name[0].isalpha():
                    continue
            files.append(p)

        # If no files found at top level, try sroie_* pattern
        if not files:
            files = list(input_path.glob("sroie_*.json"))
        if not files:
            files = list(input_path.glob("vn_*.json"))

        return sorted(files)

    def process_single(self, invoice_path: Path, bank_transactions: list[dict[str, Any]] | None) -> dict[str, Any]:
        """Process single invoice file."""
        try:
            copilot = ERPXAccountingCopilot(strict_mode=self.strict_mode)

            with open(invoice_path, encoding="utf-8") as f:
                data = json.load(f)

            # Extract OCR text
            ocr_text = data.get("text", "")

            # Extract structured fields (invoice_data or labels)
            structured_fields = data.get("invoice_data") or data.get("labels")

            # File metadata
            file_metadata = {
                "source_file": data.get("source_file", str(invoice_path)),
                "doc_id": data.get("doc_id", invoice_path.stem),
            }

            # Process using new API
            result = copilot.process(
                ocr_text=ocr_text,
                structured_fields=structured_fields,
                file_metadata=file_metadata,
                bank_txns=bank_transactions,
            )
            result["source_file"] = str(invoice_path)
            result["doc_id"] = data.get("doc_id", invoice_path.stem)

            return result

        except Exception as e:
            logger.error(f"Error processing {invoice_path}: {e}")
            return {
                "source_file": str(invoice_path),
                "error": str(e),
                "needs_human_review": True,
                "warnings": [f"Processing error: {str(e)}"],
                "missing_fields": [],
            }

    def process_batch(
        self, input_path: str, bank_transactions_path: str | None = None, output_dir: str | None = None
    ) -> dict[str, Any]:
        """
        Process batch of invoices.

        Args:
            input_path: Directory or file path
            bank_transactions_path: Optional path to bank transactions
            output_dir: Output directory for results

        Returns:
            Batch summary statistics
        """
        # Find invoice files
        invoice_files = self.find_invoice_files(input_path)
        logger.info(f"Found {len(invoice_files)} invoice files")

        if not invoice_files:
            return {"error": "No invoice files found", "total": 0}

        # Load bank transactions if provided
        bank_transactions = None
        if bank_transactions_path:
            bank_transactions = self.load_bank_transactions(bank_transactions_path)
            logger.info(f"Loaded {len(bank_transactions)} bank transactions")

        # Setup output directory
        if output_dir:
            output_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"/root/erp-ai/data/processed/asof_batch_{timestamp}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Process files
        stats = {
            "total": len(invoice_files),
            "processed": 0,
            "needs_review": 0,
            "errors": 0,
            "matched_reconciliations": 0,
            "missing_fields_summary": {},
            "warnings_summary": {},
        }

        all_results = []

        # Process with thread pool
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_file = {executor.submit(self.process_single, f, bank_transactions): f for f in invoice_files}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]

                try:
                    result = future.result()
                    all_results.append(result)

                    stats["processed"] += 1

                    if result.get("error"):
                        stats["errors"] += 1
                    elif result.get("needs_human_review"):
                        stats["needs_review"] += 1

                    # Count reconciliation matches
                    recon = result.get("reconciliation_result", {})
                    if recon.get("matched"):
                        stats["matched_reconciliations"] += len(recon["matched"])

                    # Aggregate missing fields
                    for field in result.get("missing_fields", []):
                        stats["missing_fields_summary"][field] = stats["missing_fields_summary"].get(field, 0) + 1

                    # Aggregate warnings
                    for warning in result.get("warnings", []):
                        key = warning[:50]  # Truncate for grouping
                        stats["warnings_summary"][key] = stats["warnings_summary"].get(key, 0) + 1

                    # Save individual result
                    doc_id = result.get("doc_id", file_path.stem)
                    result_file = output_dir / f"{doc_id}_asof.json"
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

                    logger.info(
                        f"[{stats['processed']}/{stats['total']}] {doc_id} - review={result.get('needs_human_review')}"
                    )

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    stats["errors"] += 1

        # Calculate percentages
        if stats["total"] > 0:
            stats["review_rate"] = stats["needs_review"] / stats["total"] * 100
            stats["error_rate"] = stats["errors"] / stats["total"] * 100
            stats["success_rate"] = (stats["total"] - stats["errors"]) / stats["total"] * 100

        # Save batch summary
        stats["output_dir"] = str(output_dir)
        summary_file = output_dir / "batch_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        # Generate markdown report
        report = self._generate_report(stats, all_results)
        report_file = output_dir / "batch_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info("=" * 60)
        logger.info("ASOFT-T Batch Processing Complete")
        logger.info("=" * 60)
        logger.info(f"  Total: {stats['total']}")
        logger.info(f"  Processed: {stats['processed']}")
        logger.info(f"  Needs Review: {stats['needs_review']} ({stats.get('review_rate', 0):.1f}%)")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info(f"  Reconciliation Matches: {stats['matched_reconciliations']}")
        logger.info(f"  Output: {output_dir}")
        logger.info("=" * 60)

        return stats

    def _generate_report(self, stats: dict[str, Any], results: list[dict[str, Any]]) -> str:
        """Generate markdown batch report."""
        report = f"""# ASOFT-T Batch Processing Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Documents | {stats["total"]} |
| Processed | {stats["processed"]} |
| Needs Human Review | {stats["needs_review"]} ({stats.get("review_rate", 0):.1f}%) |
| Errors | {stats["errors"]} ({stats.get("error_rate", 0):.1f}%) |
| Reconciliation Matches | {stats["matched_reconciliations"]} |

## Missing Fields Summary

| Field | Count |
|-------|-------|
"""
        for field, count in sorted(stats.get("missing_fields_summary", {}).items(), key=lambda x: -x[1]):
            report += f"| {field} | {count} |\n"

        report += """
## Documents Requiring Review

| Doc ID | Reason |
|--------|--------|
"""
        for result in results[:20]:  # First 20
            if result.get("needs_human_review"):
                doc_id = result.get("doc_id", "unknown")
                reasons = result.get("warnings", []) or ["Missing required fields"]
                report += f"| {doc_id} | {reasons[0][:50] if reasons else 'N/A'} |\n"

        report += f"""
## Output Location

```
{stats.get("output_dir", "N/A")}
```

---
*Report generated by ASOFT-T Batch Processor*
"""
        return report


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ASOFT-T Batch Processor")
    parser.add_argument("input_path", help="Directory or file path with invoice JSONs")
    parser.add_argument("--bank-txns", help="Path to bank transactions (JSON or CSV)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--concurrency", "-c", type=int, default=4, help="Number of workers")
    parser.add_argument("--strict", action="store_true", help="Strict mode (require Serial/No)")

    args = parser.parse_args()

    processor = ASOFTBatchProcessor(concurrency=args.concurrency, strict_mode=args.strict)

    stats = processor.process_batch(args.input_path, args.bank_txns, args.output)

    # Print final summary
    print(
        json.dumps(
            {
                "total": stats["total"],
                "processed": stats["processed"],
                "needs_review": stats["needs_review"],
                "review_rate": f"{stats.get('review_rate', 0):.1f}%",
                "output_dir": stats.get("output_dir"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
