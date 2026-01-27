
import io
import time
import sys
import unittest
from unittest.mock import MagicMock, patch
import fitz
from PIL import Image

# Mock pytesseract before importing src.processing
sys.modules["pytesseract"] = MagicMock()
sys.modules["paddleocr"] = MagicMock()

from src.processing import process_scanned_pdf, ProcessingResult

def create_dummy_pdf(pages=5):
    """Create a dummy PDF with text and noise to simulate scanned doc"""
    doc = fitz.open()
    import random

    for i in range(pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"This is page {i+1} of the dummy PDF.", fontsize=12)

        # Add many shapes/lines to simulate complexity/noise and prevent trivial PNG compression
        for _ in range(200):
            x1 = random.randint(0, 500)
            y1 = random.randint(0, 700)
            x2 = random.randint(0, 500)
            y2 = random.randint(0, 700)
            color = (random.random(), random.random(), random.random())
            page.draw_line((x1, y1), (x2, y2), color=color, width=1)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def benchmark():
    print("Preparing benchmark...")
    pdf_data = create_dummy_pdf(pages=20)

    # Mock extract_key_fields to be fast
    with patch("src.processing.extract_key_fields", return_value={}), \
         patch("src.processing.get_ocr_engine", return_value=None):
        # We need to patch process_image_ocr because we want to measure the impact
        # of the image conversion occurring BEFORE/INSIDE process_scanned_pdf
        # calling process_image_ocr, AND the image opening inside process_image_ocr.

        # Actually, the inefficiency is:
        # 1. process_scanned_pdf: pix.tobytes("png")  <-- expensive encode
        # 2. process_image_ocr: Image.open(io.BytesIO(data)) <-- expensive decode

        # So we want to run the real logic of these functions, but mock the ACTUAL OCR
        # (pytesseract.image_to_string) because that's slow and not what we are optimizing.

        # The src.processing import already mocked pytesseract at module level.
        # So pytesseract.image_to_string is already a Mock.

        print("Running benchmark on 20 pages...")
        start_time = time.time()

        # Run multiple iterations to get a stable number
        iterations = 5
        for i in range(iterations):
            result = process_scanned_pdf(pdf_data)
            assert result.success

        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / iterations

        print(f"Total time for {iterations} iterations: {total_time:.4f}s")
        print(f"Average time per iteration: {avg_time:.4f}s")
        print(f"Average time per page: {avg_time/20:.4f}s")

if __name__ == "__main__":
    benchmark()
