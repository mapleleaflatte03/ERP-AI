#!/usr/bin/env python3
"""
Kaggle Pilot Smoke Test for ERPX AI Accounting Pipeline
========================================================
Processes 20 documents from Kaggle datasets through:
1. OCR Pipeline (PaddleOCR)
2. Accounting Coding Agent

Outputs:
- data/processed/pilot_run_<timestamp>/
- reports/kaggle_pilot_summary.md
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root
sys.path.insert(0, "/root/erp-ai")

from services.ocr.ocr_pipeline import OCRPipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("KagglePilotTest")

# Paths
PROJECT_ROOT = Path("/root/erp-ai")
SROIE_RAW_PATH = PROJECT_ROOT / "data/raw_kaggle/sroie"
VN_RAW_PATH = PROJECT_ROOT / "data/raw_kaggle/vietnamese_receipts"


def load_raw_meta(meta_path: Path) -> list[dict[str, Any]]:
    """Load raw_meta.jsonl file."""
    docs = []
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    docs.append(json.loads(line))
    return docs


def run_ocr_on_image(ocr_pipeline: OCRPipeline, image_path: str) -> dict[str, Any]:
    """Run OCR on a single image."""
    try:
        result = ocr_pipeline.process_file(image_path)
        return result
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return {"error": str(e), "source_file": image_path, "text": ""}


def create_invoice_json(doc: dict[str, Any], ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Create invoice JSON combining raw labels with OCR text."""
    labels = doc.get("labels", {}) or {}

    invoice_json = {
        "doc_id": doc.get("doc_id"),
        "source": doc.get("source"),
        "source_file": doc.get("file_path"),
        "doc_type": doc.get("doc_type_guess", "receipt"),
        "text": ocr_result.get("text", ""),
        "ocr_blocks": ocr_result.get("blocks", []),
        "ocr_confidence": ocr_result.get("avg_confidence"),
        # Structured invoice_data for coding agent
        "invoice_data": {
            "invoice_no": None,  # SROIE doesn't have invoice numbers
            "date": labels.get("invoice_date"),
            "partner_name": labels.get("seller_name"),
            "total": None,  # Will be parsed from total_amount
            "vat": None,
            "grand_total": None,
            "vat_rate": None,
            "doc_type": "receipt",
            "items": [],
        },
        "labels": labels,
        "processed_at": datetime.now().isoformat(),
    }

    # Parse total_amount
    total_str = labels.get("total_amount", "")
    if total_str:
        try:
            # Remove currency symbols, commas, etc.
            amount_clean = total_str.replace(",", "").replace("RM", "").replace("$", "").strip()
            invoice_json["invoice_data"]["grand_total"] = float(amount_clean)
            invoice_json["invoice_data"]["total"] = float(amount_clean)  # Assume no VAT split
        except (ValueError, AttributeError):
            pass

    return invoice_json


def run_pilot_test(num_docs: int = 20, dataset: str = "sroie") -> dict[str, Any]:
    """
    Run pilot test on Kaggle documents.

    Args:
        num_docs: Number of documents to process
        dataset: "sroie" or "vietnamese"

    Returns:
        Summary statistics
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / f"data/processed/pilot_run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select dataset
    if dataset == "sroie":
        raw_path = SROIE_RAW_PATH
        meta_file = raw_path / "raw_meta.jsonl"
    else:
        raw_path = VN_RAW_PATH
        meta_file = raw_path / "raw_meta.jsonl"

    if not meta_file.exists():
        logger.error(f"Meta file not found: {meta_file}")
        return {"error": f"Meta file not found: {meta_file}"}

    # Load documents
    docs = load_raw_meta(meta_file)
    logger.info(f"Loaded {len(docs)} documents from {meta_file}")

    # Limit to num_docs
    docs_to_process = docs[:num_docs]

    # Initialize OCR pipeline
    logger.info("Initializing OCR pipeline...")
    ocr_pipeline = OCRPipeline(upload_dir=str(raw_path / "raw_files"), output_dir=str(output_dir / "ocr_results"))

    # Stats
    stats = {
        "timestamp": timestamp,
        "dataset": dataset,
        "total_requested": num_docs,
        "total_processed": 0,
        "total_ocr_success": 0,
        "total_ocr_failed": 0,
        "total_with_labels": 0,
        "total_text_chars": 0,
        "errors": [],
        "documents": [],
    }

    # Process each document
    for idx, doc in enumerate(docs_to_process):
        doc_id = doc.get("doc_id", f"doc_{idx}")
        file_path = doc.get("file_path")

        logger.info(f"[{idx + 1}/{num_docs}] Processing {doc_id}")

        doc_stats = {
            "doc_id": doc_id,
            "file_path": file_path,
            "ocr_success": False,
            "has_labels": bool(doc.get("labels")),
            "text_length": 0,
            "error": None,
        }

        # Skip if no file path
        if not file_path:
            doc_stats["error"] = "No file path"
            stats["errors"].append(f"{doc_id}: No file path")
            stats["documents"].append(doc_stats)
            continue

        # Resolve full image path
        full_image_path = raw_path / file_path
        if not full_image_path.exists():
            doc_stats["error"] = f"Image not found: {full_image_path}"
            stats["errors"].append(f"{doc_id}: Image not found")
            stats["documents"].append(doc_stats)
            stats["total_ocr_failed"] += 1
            continue

        # Run OCR
        try:
            ocr_result = run_ocr_on_image(ocr_pipeline, str(full_image_path))

            if ocr_result.get("error"):
                doc_stats["error"] = ocr_result["error"]
                stats["total_ocr_failed"] += 1
            else:
                doc_stats["ocr_success"] = True
                doc_stats["text_length"] = len(ocr_result.get("text", ""))
                stats["total_ocr_success"] += 1
                stats["total_text_chars"] += doc_stats["text_length"]

            # Create invoice JSON
            invoice_json = create_invoice_json(doc, ocr_result)

            # Save invoice JSON
            invoice_file = output_dir / f"{doc_id}.json"
            with open(invoice_file, "w", encoding="utf-8") as f:
                json.dump(invoice_json, f, ensure_ascii=False, indent=2)

            doc_stats["output_file"] = str(invoice_file)

        except Exception as e:
            doc_stats["error"] = str(e)
            stats["errors"].append(f"{doc_id}: {e}")
            stats["total_ocr_failed"] += 1

        if doc.get("labels"):
            stats["total_with_labels"] += 1

        stats["documents"].append(doc_stats)
        stats["total_processed"] += 1

    # Calculate summary metrics
    stats["avg_text_length"] = (
        stats["total_text_chars"] / stats["total_ocr_success"] if stats["total_ocr_success"] > 0 else 0
    )
    stats["ocr_success_rate"] = (
        stats["total_ocr_success"] / stats["total_processed"] * 100 if stats["total_processed"] > 0 else 0
    )

    # Save summary
    summary_file = output_dir / "pilot_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    stats["output_dir"] = str(output_dir)
    stats["summary_file"] = str(summary_file)

    logger.info("=" * 60)
    logger.info(f"Pilot Test Complete: {dataset}")
    logger.info("=" * 60)
    logger.info(f"  Processed: {stats['total_processed']}/{num_docs}")
    logger.info(f"  OCR Success: {stats['total_ocr_success']} ({stats['ocr_success_rate']:.1f}%)")
    logger.info(f"  OCR Failed: {stats['total_ocr_failed']}")
    logger.info(f"  With Labels: {stats['total_with_labels']}")
    logger.info(f"  Avg Text Length: {stats['avg_text_length']:.0f} chars")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 60)

    return stats


def generate_report(stats: dict[str, Any]) -> str:
    """Generate markdown report from pilot test stats."""
    report = f"""# Kaggle Pilot Test Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Dataset:** {stats.get("dataset", "unknown")}
**Timestamp:** {stats.get("timestamp", "N/A")}

## Summary Metrics

| Metric | Value |
|--------|-------|
| Documents Requested | {stats.get("total_requested", 0)} |
| Documents Processed | {stats.get("total_processed", 0)} |
| OCR Success | {stats.get("total_ocr_success", 0)} ({stats.get("ocr_success_rate", 0):.1f}%) |
| OCR Failed | {stats.get("total_ocr_failed", 0)} |
| With Labels | {stats.get("total_with_labels", 0)} |
| Avg Text Length | {stats.get("avg_text_length", 0):.0f} chars |

## Output Location

```
{stats.get("output_dir", "N/A")}
```

## Errors ({len(stats.get("errors", []))})

"""

    errors = stats.get("errors", [])
    if errors:
        for err in errors[:10]:
            report += f"- {err}\n"
        if len(errors) > 10:
            report += f"\n... and {len(errors) - 10} more errors\n"
    else:
        report += "No errors encountered.\n"

    report += """
## Sample Documents

| Doc ID | OCR Success | Text Length | Has Labels |
|--------|-------------|-------------|------------|
"""

    for doc in stats.get("documents", [])[:10]:
        success = "✅" if doc.get("ocr_success") else "❌"
        has_labels = "✅" if doc.get("has_labels") else "❌"
        report += f"| {doc.get('doc_id', 'N/A')} | {success} | {doc.get('text_length', 0)} | {has_labels} |\n"

    return report


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Kaggle Pilot Smoke Test")
    parser.add_argument("--num-docs", type=int, default=20, help="Number of documents to process")
    parser.add_argument("--dataset", choices=["sroie", "vietnamese"], default="sroie", help="Dataset to use")

    args = parser.parse_args()

    # Run pilot test
    stats = run_pilot_test(num_docs=args.num_docs, dataset=args.dataset)

    # Generate report
    report = generate_report(stats)

    # Save report
    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"kaggle_pilot_{stats.get('dataset', 'unknown')}_{stats.get('timestamp', 'unknown')}.md"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"Report saved to: {report_file}")

    # Print summary JSON
    print(
        json.dumps(
            {
                "total_processed": stats.get("total_processed"),
                "ocr_success_rate": stats.get("ocr_success_rate"),
                "output_dir": stats.get("output_dir"),
                "report_file": str(report_file),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
