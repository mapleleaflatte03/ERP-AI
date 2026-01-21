#!/usr/bin/env python3
"""
SROIE Dataset Adapter for ERPX AI Accounting
=============================================
Converts SROIE receipt dataset to ERPX RAW/Staging format.

SROIE Labels:
- company: Vendor/Seller name
- date: Invoice/receipt date
- address: Vendor address
- total: Total amount

Output format (raw_meta.jsonl):
{
    "doc_id": "sroie_X51005255805",
    "source": "kaggle/sroie-datasetv2",
    "file_path": "raw_files/X51005255805.jpg",
    "doc_type_guess": "receipt",
    "ocr_text": "...",
    "labels": {
        "seller_name": "...",
        "invoice_date": "...",
        "address": "...",
        "total_amount": "..."
    }
}
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SROIEAdapter")

# Paths
PROJECT_ROOT = Path("/root/erp-ai")
KAGGLE_SROIE_PATH = PROJECT_ROOT / "data/kaggle/sroie-datasetv2/SROIE2019"
RAW_OUTPUT_PATH = PROJECT_ROOT / "data/raw_kaggle/sroie"


def parse_entity_file(entity_path: Path) -> dict[str, str] | None:
    """Parse SROIE entity JSON file."""
    try:
        with open(entity_path, encoding="utf-8") as f:
            content = f.read().strip()
            # Handle both JSON and line-by-line format
            if content.startswith("{"):
                return json.loads(content)
            else:
                # Line format: key: value
                labels = {}
                for line in content.split("\n"):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        labels[key.strip().lower()] = val.strip()
                return labels
    except Exception as e:
        logger.warning(f"Failed to parse {entity_path}: {e}")
        return None


def parse_box_file(box_path: Path) -> str:
    """Parse SROIE box file to extract OCR text."""
    try:
        with open(box_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Box format: x1,y1,x2,y2,x3,y3,x4,y4,text
        texts = []
        for line in lines:
            parts = line.strip().split(",")
            if len(parts) >= 9:
                text = ",".join(parts[8:])  # Text may contain commas
                texts.append(text)

        return "\n".join(texts)
    except Exception as e:
        logger.warning(f"Failed to parse {box_path}: {e}")
        return ""


def adapt_sroie_dataset(
    splits: list[str] = ["train", "test"], max_docs: int | None = None, copy_images: bool = True
) -> dict[str, Any]:
    """
    Adapt SROIE dataset to ERPX RAW format.

    Args:
        splits: Which splits to process ("train", "test")
        max_docs: Maximum documents to process (None = all)
        copy_images: Whether to copy images to raw_files/

    Returns:
        Summary statistics
    """
    # Create output directories
    raw_files_dir = RAW_OUTPUT_PATH / "raw_files"
    raw_files_dir.mkdir(parents=True, exist_ok=True)

    meta_file = RAW_OUTPUT_PATH / "raw_meta.jsonl"

    stats = {"total_processed": 0, "total_with_labels": 0, "total_with_ocr": 0, "total_copied": 0, "errors": []}

    with open(meta_file, "w", encoding="utf-8") as meta_out:
        for split in splits:
            img_dir = KAGGLE_SROIE_PATH / split / "img"
            entity_dir = KAGGLE_SROIE_PATH / split / "entities"
            box_dir = KAGGLE_SROIE_PATH / split / "box"

            if not img_dir.exists():
                logger.warning(f"Image directory not found: {img_dir}")
                continue

            logger.info(f"Processing {split} split from {img_dir}")

            image_files = sorted(img_dir.glob("*.jpg"))

            for idx, img_path in enumerate(image_files):
                if max_docs and stats["total_processed"] >= max_docs:
                    break

                doc_id = f"sroie_{img_path.stem}"

                # Parse labels
                entity_path = entity_dir / f"{img_path.stem}.txt"
                labels = None
                if entity_path.exists():
                    raw_labels = parse_entity_file(entity_path)
                    if raw_labels:
                        labels = {
                            "seller_name": raw_labels.get("company"),
                            "invoice_date": raw_labels.get("date"),
                            "address": raw_labels.get("address"),
                            "total_amount": raw_labels.get("total"),
                        }
                        stats["total_with_labels"] += 1

                # Parse OCR text
                box_path = box_dir / f"{img_path.stem}.txt"
                ocr_text = ""
                if box_path.exists():
                    ocr_text = parse_box_file(box_path)
                    if ocr_text:
                        stats["total_with_ocr"] += 1

                # Copy image
                dest_file_path = f"raw_files/{img_path.name}"
                if copy_images:
                    dest_full_path = RAW_OUTPUT_PATH / dest_file_path
                    try:
                        shutil.copy2(img_path, dest_full_path)
                        stats["total_copied"] += 1
                    except Exception as e:
                        stats["errors"].append(f"Copy error {img_path.name}: {e}")

                # Build metadata record
                record = {
                    "doc_id": doc_id,
                    "source": "kaggle/sroie-datasetv2",
                    "file_path": dest_file_path,
                    "doc_type_guess": "receipt",
                    "split": split,
                    "ocr_text": ocr_text if ocr_text else None,
                    "labels": labels,
                }

                meta_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                stats["total_processed"] += 1

                if (idx + 1) % 100 == 0:
                    logger.info(f"  Processed {idx + 1} documents from {split}")

    # Write summary
    stats["output_path"] = str(RAW_OUTPUT_PATH)
    stats["meta_file"] = str(meta_file)

    summary_path = RAW_OUTPUT_PATH / "adapter_summary.json"
    with open(summary_path, "w") as f:
        json.dump(stats, f, indent=2)

    logger.info(f"SROIE Adapter complete: {stats['total_processed']} docs")
    logger.info(f"  With labels: {stats['total_with_labels']}")
    logger.info(f"  With OCR: {stats['total_with_ocr']}")
    logger.info(f"  Output: {RAW_OUTPUT_PATH}")

    return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SROIE Dataset Adapter")
    parser.add_argument("--max-docs", type=int, default=None, help="Max documents to process")
    parser.add_argument("--no-copy", action="store_true", help="Skip copying images")
    parser.add_argument("--splits", nargs="+", default=["train", "test"], help="Splits to process")

    args = parser.parse_args()

    stats = adapt_sroie_dataset(splits=args.splits, max_docs=args.max_docs, copy_images=not args.no_copy)

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
