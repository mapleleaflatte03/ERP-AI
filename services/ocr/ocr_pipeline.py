"""
OCR Pipeline Service for ERP AI
Processes PDF/Image files and extracts text using PaddleOCR + pdfplumber
CPU-only mode
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Set environment variables before imports
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_cuda"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import pdfplumber
from PIL import Image
from pypdf import PdfReader

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("OCR-Pipeline")

# Lazy load PaddleOCR to avoid slow startup
_ocr_engine = None


def get_ocr_engine():
    """Lazy load PaddleOCR engine (CPU mode)"""
    global _ocr_engine
    if _ocr_engine is None:
        logger.info("Initializing PaddleOCR engine (CPU mode)...")
        from paddleocr import PaddleOCR

        # PaddleOCR 2.x API
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang="vi",  # Vietnamese support
            use_gpu=False,
            show_log=False,
        )
        logger.info("PaddleOCR engine initialized successfully")
    return _ocr_engine


class OCRPipeline:
    """Main OCR Pipeline class"""

    def __init__(self, upload_dir: str = None, output_dir: str = None):
        self.base_dir = Path(os.environ.get("ERP_AI_DIR", "/root/erp-ai"))
        self.upload_dir = Path(upload_dir) if upload_dir else self.base_dir / "data" / "uploads"
        self.output_dir = Path(output_dir) if output_dir else self.base_dir / "data" / "processed"

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("OCR Pipeline initialized")
        logger.info(f"  Upload dir: {self.upload_dir}")
        logger.info(f"  Output dir: {self.output_dir}")

    def process_file(self, file_path: str) -> dict[str, Any]:
        """
        Process a PDF or image file

        Args:
            file_path: Path to the input file

        Returns:
            Dictionary containing OCR results
        """
        file_path = Path(file_path)

        # Check file exists
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return self._create_error_result(str(file_path), error_msg)

        logger.info(f"Processing file: {file_path}")

        # Determine file type
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                result = self._process_pdf(file_path)
            elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                result = self._process_image(file_path)
            else:
                error_msg = f"Unsupported file type: {suffix}"
                logger.error(error_msg)
                return self._create_error_result(str(file_path), error_msg)

            # Save result to JSON
            output_path = self._save_result(result, file_path.stem)
            result["output_file"] = str(output_path)

            logger.info(f"Processing completed. Output: {output_path}")
            return result

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.exception(error_msg)
            return self._create_error_result(str(file_path), error_msg)

    def _process_pdf(self, file_path: Path) -> dict[str, Any]:
        """Process PDF file using pdfplumber + PaddleOCR"""
        logger.info(f"Processing PDF: {file_path.name}")

        result = {
            "id": str(uuid.uuid4()),
            "source_file": str(file_path),
            "file_type": "pdf",
            "processed_at": datetime.now().isoformat(),
            "pages": [],
            "text": "",
            "blocks": [],
            "errors": [],
            "metadata": {},
        }

        all_text = []
        all_blocks = []

        # Get PDF metadata
        try:
            pdf_reader = PdfReader(str(file_path))
            result["metadata"] = {
                "page_count": len(pdf_reader.pages),
                "pdf_info": dict(pdf_reader.metadata) if pdf_reader.metadata else {},
            }
        except Exception as e:
            result["errors"].append(f"Metadata extraction failed: {str(e)}")

        # Process with pdfplumber (for text extraction)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    logger.info(f"  Processing page {page_num}/{len(pdf.pages)}")

                    page_result = {
                        "page_number": page_num,
                        "width": page.width,
                        "height": page.height,
                        "text": "",
                        "blocks": [],
                        "method": "pdfplumber",
                    }

                    # Extract text using pdfplumber
                    text = page.extract_text() or ""

                    # If pdfplumber returns empty, try OCR
                    if len(text.strip()) < 10:
                        logger.info(f"    Page {page_num}: Low text content, trying OCR...")
                        page_result["method"] = "paddleocr"

                        # Convert page to image for OCR
                        try:
                            img = page.to_image(resolution=150)
                            img_array = np.array(img.original)

                            # Run OCR
                            ocr_engine = get_ocr_engine()
                            ocr_result = ocr_engine.ocr(img_array, cls=True)

                            if ocr_result and ocr_result[0]:
                                ocr_texts = []
                                for line in ocr_result[0]:
                                    bbox = line[0]
                                    text_content = line[1][0]
                                    confidence = line[1][1]

                                    ocr_texts.append(text_content)
                                    page_result["blocks"].append(
                                        {"bbox": bbox, "text": text_content, "confidence": float(confidence)}
                                    )

                                text = "\n".join(ocr_texts)
                        except Exception as ocr_error:
                            result["errors"].append(f"OCR failed on page {page_num}: {str(ocr_error)}")
                    else:
                        # Extract words with positions from pdfplumber
                        words = page.extract_words() or []
                        for word in words[:100]:  # Limit to first 100 words for blocks
                            page_result["blocks"].append(
                                {
                                    "bbox": [
                                        [word["x0"], word["top"]],
                                        [word["x1"], word["top"]],
                                        [word["x1"], word["bottom"]],
                                        [word["x0"], word["bottom"]],
                                    ],
                                    "text": word["text"],
                                    "confidence": 1.0,  # pdfplumber text is native PDF
                                }
                            )

                    page_result["text"] = text
                    all_text.append(text)
                    all_blocks.extend(page_result["blocks"])
                    result["pages"].append(page_result)

        except Exception as e:
            result["errors"].append(f"PDF processing failed: {str(e)}")

        result["text"] = "\n\n".join(all_text)
        result["blocks"] = all_blocks

        # Calculate average confidence
        if all_blocks:
            confidences = [b["confidence"] for b in all_blocks if "confidence" in b]
            result["avg_confidence"] = sum(confidences) / len(confidences) if confidences else 0

        return result

    def _process_image(self, file_path: Path) -> dict[str, Any]:
        """Process image file using PaddleOCR"""
        logger.info(f"Processing image: {file_path.name}")

        result = {
            "id": str(uuid.uuid4()),
            "source_file": str(file_path),
            "file_type": "image",
            "processed_at": datetime.now().isoformat(),
            "pages": [],
            "text": "",
            "blocks": [],
            "errors": [],
            "metadata": {},
        }

        try:
            # Load image
            img = Image.open(file_path)
            result["metadata"] = {"width": img.width, "height": img.height, "format": img.format, "mode": img.mode}

            # Convert to numpy array
            img_array = np.array(img.convert("RGB"))

            # Run OCR
            ocr_engine = get_ocr_engine()
            ocr_result = ocr_engine.ocr(img_array, cls=True)

            page_result = {
                "page_number": 1,
                "width": img.width,
                "height": img.height,
                "text": "",
                "blocks": [],
                "method": "paddleocr",
            }

            if ocr_result and ocr_result[0]:
                texts = []
                for line in ocr_result[0]:
                    bbox = line[0]
                    text_content = line[1][0]
                    confidence = line[1][1]

                    texts.append(text_content)
                    block = {"bbox": bbox, "text": text_content, "confidence": float(confidence)}
                    page_result["blocks"].append(block)
                    result["blocks"].append(block)

                page_result["text"] = "\n".join(texts)
                result["text"] = page_result["text"]

            result["pages"].append(page_result)

            # Calculate average confidence
            if result["blocks"]:
                confidences = [b["confidence"] for b in result["blocks"]]
                result["avg_confidence"] = sum(confidences) / len(confidences)

        except Exception as e:
            result["errors"].append(f"Image processing failed: {str(e)}")

        return result

    def _create_error_result(self, file_path: str, error: str) -> dict[str, Any]:
        """Create an error result"""
        return {
            "id": str(uuid.uuid4()),
            "source_file": file_path,
            "file_type": "unknown",
            "processed_at": datetime.now().isoformat(),
            "pages": [],
            "text": "",
            "blocks": [],
            "errors": [error],
            "metadata": {},
        }

    def _save_result(self, result: dict[str, Any], base_name: str) -> Path:
        """Save result to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{base_name}_{timestamp}.json"
        output_path = self.output_dir / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return output_path


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python ocr_pipeline.py <file_path>")
        print("  file_path: Path to PDF or image file")
        sys.exit(1)

    file_path = sys.argv[1]

    # Initialize pipeline
    pipeline = OCRPipeline()

    # Process file
    result = pipeline.process_file(file_path)

    # Print summary
    print("\n" + "=" * 60)
    print("OCR Processing Complete")
    print("=" * 60)
    print(f"Source: {result.get('source_file', 'N/A')}")
    print(f"Pages: {len(result.get('pages', []))}")
    print(f"Text length: {len(result.get('text', ''))} characters")
    print(f"Blocks: {len(result.get('blocks', []))}")
    if result.get("avg_confidence"):
        print(f"Avg confidence: {result['avg_confidence']:.2%}")
    if result.get("errors"):
        print(f"Errors: {result['errors']}")
    print(f"Output: {result.get('output_file', 'N/A')}")
    print("=" * 60)

    return result


if __name__ == "__main__":
    main()
