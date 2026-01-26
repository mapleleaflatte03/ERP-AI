"""
ERPX AI Accounting - Document Processing Module
================================================
OCR, PDF, and Excel document processing.
"""

import io
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Document Processing Result
# =============================================================================


@dataclass
class ProcessingResult:
    """Result of document processing"""

    success: bool
    document_text: str
    tables: list[list[list[str]]]  # List of tables, each table is list of rows
    key_fields: dict[str, Any]
    confidence: float
    extraction_method: str
    page_count: int = 1
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "document_text": self.document_text,
            "tables": self.tables,
            "key_fields": self.key_fields,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "page_count": self.page_count,
            "error_message": self.error_message,
        }


# =============================================================================
# OCR Processing (PaddleOCR)
# =============================================================================

_ocr_engine = None


def get_ocr_engine():
    """Get or create PaddleOCR engine"""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR

            _ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang="vi",  # Vietnamese
                use_gpu=False,  # CPU only
                show_log=False,
            )
            logger.info("PaddleOCR engine initialized")
        except ImportError:
            logger.warning("PaddleOCR not available, falling back to basic extraction")
            _ocr_engine = None
    return _ocr_engine


def process_image_ocr(image_data: bytes) -> ProcessingResult:
    """Process image with OCR"""
    ocr = get_ocr_engine()

    if ocr is None:
        # Fallback: try with pytesseract
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang="vie+eng")

            return ProcessingResult(
                success=True,
                document_text=text,
                tables=[],
                key_fields=extract_key_fields(text),
                confidence=0.80,
                extraction_method="tesseract",
            )

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return ProcessingResult(
                success=False,
                document_text="",
                tables=[],
                key_fields={},
                confidence=0.0,
                extraction_method="failed",
                error_message=str(e),
            )


# =============================================================================
# PDF Processing
# =============================================================================


def process_pdf(pdf_data: bytes) -> ProcessingResult:
    """Process PDF document"""
    try:
        import pdfplumber

        pdf_file = io.BytesIO(pdf_data)
        all_text = []
        all_tables = []
        page_count = 0

        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages):
                # Extract text
                text = page.extract_text()
                if text:
                    all_text.append(f"--- Page {page_num + 1} ---\n{text}")

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table:
                            all_tables.append(table)

        full_text = "\n\n".join(all_text)

        # If no text extracted, PDF might be scanned - try OCR
        if not full_text.strip():
            logger.info("PDF appears to be scanned, attempting OCR")
            return process_scanned_pdf(pdf_data)

        return ProcessingResult(
            success=True,
            document_text=full_text,
            tables=all_tables,
            key_fields=extract_key_fields(full_text),
            confidence=0.9,
            extraction_method="pdfplumber",
            page_count=page_count,
        )

    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        return ProcessingResult(
            success=False,
            document_text="",
            tables=[],
            key_fields={},
            confidence=0.0,
            extraction_method="failed",
            error_message=str(e),
        )


def process_scanned_pdf(pdf_data: bytes) -> ProcessingResult:
    """Process scanned PDF by rendering pages and running OCR"""
    try:
        import fitz  # PyMuPDF

        pdf_file = io.BytesIO(pdf_data)
        doc = fitz.open(stream=pdf_file, filetype="pdf")

        all_text = []
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            # Render page to image
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")

            # OCR the image
            result = process_image_ocr(img_data)
            if result.success:
                all_text.append(f"--- Page {page_num + 1} ---\n{result.document_text}")

        doc.close()
        full_text = "\n\n".join(all_text)

        return ProcessingResult(
            success=True,
            document_text=full_text,
            tables=[],
            key_fields=extract_key_fields(full_text),
            confidence=0.75,
            extraction_method="scanned_pdf_ocr",
            page_count=page_count,
        )

    except Exception as e:
        logger.error(f"Scanned PDF processing failed: {e}")
        return ProcessingResult(
            success=False,
            document_text="",
            tables=[],
            key_fields={},
            confidence=0.0,
            extraction_method="failed",
            error_message=str(e),
        )


# =============================================================================
# Excel Processing
# =============================================================================


def process_excel(excel_data: bytes) -> ProcessingResult:
    """Process Excel file"""
    try:
        import pandas as pd

        excel_file = io.BytesIO(excel_data)

        # Read all sheets
        xl = pd.ExcelFile(excel_file)
        all_text = []
        all_tables = []

        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name)

            # Convert to text
            text = f"--- Sheet: {sheet_name} ---\n"
            text += df.to_string()
            all_text.append(text)

            # Convert to table (list of lists)
            table = [df.columns.tolist()] + df.values.tolist()
            all_tables.append(table)

        full_text = "\n\n".join(all_text)

        return ProcessingResult(
            success=True,
            document_text=full_text,
            tables=all_tables,
            key_fields=extract_key_fields_from_tables(all_tables),
            confidence=0.95,
            extraction_method="pandas_excel",
            page_count=len(xl.sheet_names),
        )

    except Exception as e:
        logger.error(f"Excel processing failed: {e}")
        return ProcessingResult(
            success=False,
            document_text="",
            tables=[],
            key_fields={},
            confidence=0.0,
            extraction_method="failed",
            error_message=str(e),
        )


# =============================================================================
# Key Field Extraction
# =============================================================================


# Vietnamese patterns
_PATTERNS = {
    # Invoice number patterns
    "invoice_number": [
        re.compile(r"Số[:\s]*(\d{7,})", re.IGNORECASE),
        re.compile(r"Invoice[:\s#]*(\w+[-/]?\d+)", re.IGNORECASE),
        re.compile(r"Mã[:\s]*(\d{7,})", re.IGNORECASE),
        re.compile(r"Số HĐ[:\s]*(\S+)", re.IGNORECASE),
    ],
    # Tax ID patterns
    "tax_id": [
        re.compile(r"MST[:\s]*(\d{10,13})", re.IGNORECASE),
        re.compile(r"Mã số thuế[:\s]*(\d{10,13})", re.IGNORECASE),
        re.compile(r"Tax ID[:\s]*(\d{10,13})", re.IGNORECASE),
    ],
    # Date patterns
    "invoice_date": [
        re.compile(r"Ngày[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"Date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", re.IGNORECASE),
    ],
    # Amount patterns (Vietnamese format with dots/commas)
    "total_amount": [
        re.compile(r"Tổng(?:\s+cộng)?[:\s]*([\d.,]+)\s*(?:VND|đ|đồng)?", re.IGNORECASE),
        re.compile(r"Total[:\s]*([\d.,]+)", re.IGNORECASE),
        re.compile(r"Thành tiền[:\s]*([\d.,]+)", re.IGNORECASE),
        re.compile(r"TỔNG TIỀN[:\s]*([\d.,]+)", re.IGNORECASE),
    ],
    # VAT patterns
    "vat_amount": [
        re.compile(r"(?:Thuế\s+)?GTGT[:\s]*([\d.,]+)", re.IGNORECASE),
        re.compile(r"VAT[:\s]*([\d.,]+)", re.IGNORECASE),
        re.compile(r"Thuế[:\s]*([\d.,]+)", re.IGNORECASE),
    ],
    # Vendor name
    "vendor_name": [
        re.compile(r"Đơn vị bán[:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"Nhà cung cấp[:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"Vendor[:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"Công ty[:\s]*(.+?)(?:\n|$)", re.IGNORECASE),
    ],
}


def extract_key_fields(text: str) -> dict[str, Any]:
    """Extract key fields from text using regex patterns"""
    fields = {}

    for field, pattern_list in _PATTERNS.items():
        for pattern in pattern_list:
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                # Clean up amount values
                if field in ["total_amount", "vat_amount"]:
                    value = parse_amount(value)
                fields[field] = value
                break

    return fields


def extract_key_fields_from_tables(tables: list[list[list[str]]]) -> dict[str, Any]:
    """Extract key fields from Excel tables"""
    fields = {}

    for table in tables:
        if not table:
            continue

        # Look for key-value pairs in first column
        for row in table:
            if len(row) >= 2:
                key = str(row[0]).lower().strip() if row[0] else ""
                value = row[1]

                if "tổng" in key or "total" in key:
                    fields["total_amount"] = parse_amount(str(value))
                elif "thuế" in key or "vat" in key or "gtgt" in key:
                    fields["vat_amount"] = parse_amount(str(value))
                elif "số" in key and "hóa đơn" in key or "invoice" in key:
                    fields["invoice_number"] = str(value)
                elif "ngày" in key or "date" in key:
                    fields["invoice_date"] = str(value)
                elif "nhà cung cấp" in key or "vendor" in key:
                    fields["vendor_name"] = str(value)

    return fields


def parse_amount(value: str) -> float | None:
    """Parse Vietnamese amount format to float"""
    if not value:
        return None

    try:
        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[^\d.,]", "", str(value))

        # Vietnamese format: 1.000.000,50 or 1,000,000.50
        if "," in cleaned and "." in cleaned:
            # Determine which is decimal separator
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")

            if last_comma > last_dot:
                # Comma is decimal separator (European/VN format)
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Dot is decimal separator (US format)
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Only commas - could be thousands or decimal
            if cleaned.count(",") == 1 and len(cleaned.split(",")[1]) <= 2:
                # Decimal separator
                cleaned = cleaned.replace(",", ".")
            else:
                # Thousands separator
                cleaned = cleaned.replace(",", "")

        return float(cleaned)
    except (ValueError, AttributeError):
        return None


# =============================================================================
# Main Processing Function
# =============================================================================


def process_document(
    file_data: bytes,
    content_type: str,
    filename: str = "",
) -> ProcessingResult:
    """
    Process document based on content type.

    Supports:
    - Images (PNG, JPG, JPEG): OCR
    - PDF: Text extraction or OCR for scanned
    - Excel (XLSX, XLS): Table parsing
    """
    logger.info(f"Processing document: {filename} ({content_type})")

    # Determine processing method based on content type
    if content_type in ["image/png", "image/jpeg", "image/jpg"]:
        return process_image_ocr(file_data)

    elif content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return process_pdf(file_data)

    elif content_type in [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ] or filename.lower().endswith((".xlsx", ".xls")):
        return process_excel(file_data)

    else:
        return ProcessingResult(
            success=False,
            document_text="",
            tables=[],
            key_fields={},
            confidence=0.0,
            extraction_method="unsupported",
            error_message=f"Unsupported content type: {content_type}",
        )


__all__ = [
    "ProcessingResult",
    "process_document",
    "process_image_ocr",
    "process_pdf",
    "process_excel",
    "extract_key_fields",
]
