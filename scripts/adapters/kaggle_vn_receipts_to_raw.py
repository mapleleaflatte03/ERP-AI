#!/usr/bin/env python3
"""
Vietnamese Receipts (MC_OCR 2021) Dataset Adapter for ERPX AI Accounting
========================================================================
Converts Vietnamese receipts dataset to ERPX RAW/Staging format.

MC_OCR 2021 Labels (category_id):
- 15: SELLER
- 16: ADDRESS
- 17: TIMESTAMP
- 18: TOTAL_COST

Output format (raw_meta.jsonl):
{
    "doc_id": "vn_mcocr_public_xxx",
    "source": "kaggle/vietnamese-receipts-mc-ocr-2021",
    "file_path": "raw_files/xxx.jpg",
    "doc_type_guess": "receipt_vn",
    "ocr_text": "...",
    "labels": {
        "seller_name": "...",
        "address": "...",
        "invoice_date": "...",
        "total_amount": "..."
    }
}
"""

import csv
import json
import logging
import shutil
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VNReceiptsAdapter")

# Paths
PROJECT_ROOT = Path("/root/erp-ai")
KAGGLE_VN_PATH = PROJECT_ROOT / "data/kaggle/vietnamese-receipts"
RAW_OUTPUT_PATH = PROJECT_ROOT / "data/raw_kaggle/vietnamese_receipts"

# Label mapping
LABEL_MAP = {"SELLER": "seller_name", "ADDRESS": "address", "TIMESTAMP": "invoice_date", "TOTAL_COST": "total_amount"}


def find_image_file(img_id: str) -> Path | None:
    """Find image file across different subdirectories."""
    possible_dirs = [
        KAGGLE_VN_PATH / "dataset/mcocr_public_train_data/mcocr_train_data",
        KAGGLE_VN_PATH / "data0.7/mcocr_public_train_data/mcocr_train_data",
        KAGGLE_VN_PATH / "data0_or_180/mcocr_public_train_data/mcocr_train_data",
        KAGGLE_VN_PATH / "kie_data/kie_data",
    ]

    for dir_path in possible_dirs:
        img_path = dir_path / img_id
        if img_path.exists():
            return img_path

    # Try recursive search (slower)
    for dir_path in possible_dirs:
        if dir_path.exists():
            matches = list(dir_path.rglob(img_id))
            if matches:
                return matches[0]

    return None


def parse_labels_from_row(anno_texts: str, anno_labels: str) -> dict[str, str]:
    """Parse labels from CSV row."""
    labels = {}

    try:
        texts = anno_texts.split("|||")
        label_names = anno_labels.split("|||")

        for text, label in zip(texts, label_names):
            mapped_label = LABEL_MAP.get(label.strip())
            if mapped_label:
                if mapped_label not in labels or not labels[mapped_label]:
                    labels[mapped_label] = text.strip()
                elif mapped_label in ["address"]:
                    # Concatenate multiple address lines
                    labels[mapped_label] += ", " + text.strip()
    except Exception as e:
        logger.warning(f"Failed to parse labels: {e}")

    return labels


def adapt_vietnamese_receipts(max_docs: int | None = None, copy_images: bool = True) -> dict[str, Any]:
    """
    Adapt Vietnamese receipts dataset to ERPX RAW format.

    Args:
        max_docs: Maximum documents to process (None = all)
        copy_images: Whether to copy images to raw_files/

    Returns:
        Summary statistics
    """
    # Create output directories
    raw_files_dir = RAW_OUTPUT_PATH / "raw_files"
    raw_files_dir.mkdir(parents=True, exist_ok=True)

    meta_file = RAW_OUTPUT_PATH / "raw_meta.jsonl"
    csv_path = KAGGLE_VN_PATH / "mcocr_train_df.csv"

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return {"error": f"CSV not found: {csv_path}"}

    stats = {
        "total_processed": 0,
        "total_with_labels": 0,
        "total_with_image": 0,
        "total_copied": 0,
        "missing_images": [],
        "errors": [],
    }

    with open(meta_file, "w", encoding="utf-8") as meta_out:
        with open(csv_path, encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)

            for idx, row in enumerate(reader):
                if max_docs and stats["total_processed"] >= max_docs:
                    break

                img_id = row.get("img_id", "")
                if not img_id:
                    continue

                doc_id = f"vn_{img_id.replace('.jpg', '').replace('.png', '')}"

                # Parse labels
                anno_texts = row.get("anno_texts", "")
                anno_labels = row.get("anno_labels", "")
                labels = parse_labels_from_row(anno_texts, anno_labels)

                if labels:
                    stats["total_with_labels"] += 1

                # Find and copy image
                img_path = find_image_file(img_id)
                dest_file_path = f"raw_files/{img_id}"

                if img_path:
                    stats["total_with_image"] += 1
                    if copy_images:
                        dest_full_path = RAW_OUTPUT_PATH / dest_file_path
                        try:
                            shutil.copy2(img_path, dest_full_path)
                            stats["total_copied"] += 1
                        except Exception as e:
                            stats["errors"].append(f"Copy error {img_id}: {e}")
                else:
                    if len(stats["missing_images"]) < 10:
                        stats["missing_images"].append(img_id)

                # Build metadata record
                record = {
                    "doc_id": doc_id,
                    "source": "kaggle/vietnamese-receipts-mc-ocr-2021",
                    "file_path": dest_file_path if img_path else None,
                    "doc_type_guess": "receipt_vn",
                    "ocr_text": anno_texts.replace("|||", "\n") if anno_texts else None,
                    "labels": labels if labels else None,
                    "image_quality": float(row.get("anno_image_quality", 0)) if row.get("anno_image_quality") else None,
                }

                meta_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                stats["total_processed"] += 1

                if (idx + 1) % 500 == 0:
                    logger.info(f"  Processed {idx + 1} documents")

    # Write summary
    stats["output_path"] = str(RAW_OUTPUT_PATH)
    stats["meta_file"] = str(meta_file)

    summary_path = RAW_OUTPUT_PATH / "adapter_summary.json"
    with open(summary_path, "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    logger.info(f"Vietnamese Receipts Adapter complete: {stats['total_processed']} docs")
    logger.info(f"  With labels: {stats['total_with_labels']}")
    logger.info(f"  With images: {stats['total_with_image']}")
    logger.info(f"  Output: {RAW_OUTPUT_PATH}")

    return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Vietnamese Receipts Dataset Adapter")
    parser.add_argument("--max-docs", type=int, default=None, help="Max documents to process")
    parser.add_argument("--no-copy", action="store_true", help="Skip copying images")

    args = parser.parse_args()

    stats = adapt_vietnamese_receipts(max_docs=args.max_docs, copy_images=not args.no_copy)

    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
