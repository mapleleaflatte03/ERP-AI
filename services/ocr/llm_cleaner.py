"""
LLM-based OCR Text Cleaning Service
====================================
Uses LLM to clean and structure raw OCR output:
- Fix OCR errors (misread characters, broken words)
- Standardize date/number formats
- Extract structured fields
- Vietnamese-specific cleaning

Integrates with DO Agent (Qwen3-32B) or fallback rules.
"""

import json
import logging
import re
from typing import Any, Optional

import requests

from core.config import settings

logger = logging.getLogger("LLM-Cleaner")

# Vietnamese character corrections (common OCR errors)
VN_CORRECTIONS = {
    "đ": ["d", "đ", "ð"],
    "ă": ["a", "ă", "â"],
    "ơ": ["o", "ơ", "ô"],
    "ư": ["u", "ư"],
    "Đ": ["D", "Đ"],
    # Number corrections
    "0": ["O", "o"],
    "1": ["l", "I", "i"],
    "5": ["S", "s"],
    "8": ["B"],
}

# Common Vietnamese business terms
VN_TERMS = {
    "hoa don": "hóa đơn",
    "dien tu": "điện tử", 
    "nha cung cap": "nhà cung cấp",
    "so tien": "số tiền",
    "ngay": "ngày",
    "thang": "tháng",
    "nam": "năm",
    "cong ty": "công ty",
    "tnhh": "TNHH",
    "cp": "CP",
    "thuê": "thuế",
    "gtgt": "GTGT",
    "vat": "VAT",
}


class LLMCleaner:
    """OCR text cleaning using LLM + rule-based fallback"""

    def __init__(self):
        self.use_llm = bool(settings.DO_AGENT_KEY and settings.DO_AGENT_URL)
        if self.use_llm:
            logger.info("LLM Cleaner initialized with DO Agent")
        else:
            logger.info("LLM Cleaner using rule-based fallback (no LLM configured)")

    def clean_ocr_text(self, raw_text: str, context: Optional[dict] = None) -> dict[str, Any]:
        """
        Clean OCR text using LLM or rules.
        
        Args:
            raw_text: Raw OCR output text
            context: Optional context (document type, expected fields)
            
        Returns:
            {
                "cleaned_text": str,
                "extracted_fields": dict,
                "confidence": float,
                "method": "llm" | "rules",
                "corrections": list
            }
        """
        if not raw_text or not raw_text.strip():
            return {
                "cleaned_text": "",
                "extracted_fields": {},
                "confidence": 0.0,
                "method": "none",
                "corrections": []
            }

        # Try LLM first if available
        if self.use_llm:
            try:
                result = self._clean_with_llm(raw_text, context)
                if result["confidence"] > 0.5:
                    return result
                logger.warning("LLM confidence low, falling back to rules")
            except Exception as e:
                logger.error(f"LLM cleaning failed: {e}, falling back to rules")

        # Fallback to rule-based cleaning
        return self._clean_with_rules(raw_text, context)

    def _clean_with_llm(self, raw_text: str, context: Optional[dict] = None) -> dict[str, Any]:
        """Clean using LLM (DO Agent)"""
        
        prompt = self._build_cleaning_prompt(raw_text, context)
        
        headers = {
            "Authorization": f"Bearer {settings.DO_AGENT_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": settings.DO_AGENT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": """You are an OCR text cleaning assistant for Vietnamese accounting documents.
Your task is to:
1. Fix OCR errors (misread characters, broken words)
2. Standardize Vietnamese text with proper diacritics
3. Extract key fields (dates, amounts, invoice numbers, vendor names)
4. Return ONLY valid JSON, no markdown or explanations.

Output format:
{
    "cleaned_text": "cleaned full text",
    "extracted_fields": {
        "invoice_number": "...",
        "invoice_date": "YYYY-MM-DD",
        "vendor_name": "...",
        "total_amount": 123456,
        "vat_amount": 12345,
        "currency": "VND"
    },
    "corrections": ["original -> fixed", ...],
    "confidence": 0.85
}"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        response = requests.post(
            f"{settings.DO_AGENT_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=settings.DO_AGENT_TIMEOUT,
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = re.sub(r'^```json?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            parsed = json.loads(content)
            parsed["method"] = "llm"
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise

    def _build_cleaning_prompt(self, raw_text: str, context: Optional[dict] = None) -> str:
        """Build prompt for LLM cleaning"""
        prompt = f"""Clean the following OCR text from a Vietnamese accounting document.

RAW OCR TEXT:
{raw_text[:3000]}  # Limit to 3000 chars

"""
        if context:
            prompt += f"""
CONTEXT:
- Document type: {context.get('doc_type', 'unknown')}
- Expected fields: {context.get('expected_fields', [])}
"""
        
        prompt += """
Return cleaned text and extracted fields as JSON only."""
        return prompt

    def _clean_with_rules(self, raw_text: str, context: Optional[dict] = None) -> dict[str, Any]:
        """Rule-based OCR cleaning fallback"""
        
        corrections = []
        cleaned = raw_text

        # 1. Fix common Vietnamese term errors
        for wrong, correct in VN_TERMS.items():
            if wrong.lower() in cleaned.lower():
                cleaned = re.sub(re.escape(wrong), correct, cleaned, flags=re.IGNORECASE)
                corrections.append(f"{wrong} -> {correct}")

        # 2. Standardize numbers (remove spaces in numbers)
        cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)
        
        # 3. Fix date formats
        # DD/MM/YYYY or DD-MM-YYYY -> standardize to DD/MM/YYYY
        cleaned = re.sub(r'(\d{1,2})[-.](\d{1,2})[-.](\d{4})', r'\1/\2/\3', cleaned)
        
        # 4. Fix currency amounts (add thousand separators)
        def fix_amount(match):
            num = match.group(0).replace(' ', '').replace('.', '').replace(',', '')
            return f"{int(num):,}".replace(',', '.')
        
        # Match large numbers that might be amounts
        cleaned = re.sub(r'\b\d{6,}\b', fix_amount, cleaned)

        # 5. Extract fields using regex patterns
        extracted_fields = self._extract_fields_regex(cleaned)

        # Calculate confidence based on extracted fields
        field_count = len([v for v in extracted_fields.values() if v])
        confidence = min(0.3 + (field_count * 0.1), 0.8)

        return {
            "cleaned_text": cleaned,
            "extracted_fields": extracted_fields,
            "confidence": confidence,
            "method": "rules",
            "corrections": corrections
        }

    def _extract_fields_regex(self, text: str) -> dict[str, Any]:
        """Extract common invoice fields using regex"""
        fields = {}

        # Invoice number patterns
        invoice_patterns = [
            r'(?:Số|So|No\.?|Number)\s*:?\s*([A-Z0-9/-]+)',
            r'Hóa đơn\s*:?\s*([A-Z0-9/-]+)',
            r'Mẫu số\s*:?\s*([A-Z0-9/-]+)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields["invoice_number"] = match.group(1).strip()
                break

        # Date patterns
        date_patterns = [
            r'(?:Ngày|Ngay|Date)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Convert to ISO format
                date_str = match.group(1)
                parts = date_str.split('/')
                if len(parts) == 3:
                    fields["invoice_date"] = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                break

        # Amount patterns
        amount_patterns = [
            r'(?:Tổng|Tong|Total|Cộng)\s*:?\s*([0-9.,]+)',
            r'(?:Số tiền|So tien|Amount)\s*:?\s*([0-9.,]+)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace('.', '').replace(',', '')
                try:
                    fields["total_amount"] = int(amount_str)
                except ValueError:
                    pass
                break

        # VAT patterns
        vat_patterns = [
            r'(?:VAT|GTGT|Thuế)\s*:?\s*([0-9.,]+)',
            r'(\d+)%',
        ]
        for pattern in vat_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                vat_str = match.group(1).replace('.', '').replace(',', '')
                try:
                    fields["vat_amount"] = int(vat_str)
                except ValueError:
                    pass
                break

        # Vendor name patterns
        vendor_patterns = [
            r'(?:Công ty|Cong ty|Company)\s*:?\s*(.+?)(?:\n|$)',
            r'(?:NCC|Nhà cung cấp|Vendor)\s*:?\s*(.+?)(?:\n|$)',
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields["vendor_name"] = match.group(1).strip()[:100]
                break

        fields["currency"] = "VND"  # Default for Vietnamese invoices

        return fields


# Singleton instance
_cleaner: Optional[LLMCleaner] = None


def get_llm_cleaner() -> LLMCleaner:
    """Get singleton LLM cleaner instance"""
    global _cleaner
    if _cleaner is None:
        _cleaner = LLMCleaner()
    return _cleaner


def clean_ocr_output(raw_text: str, context: Optional[dict] = None) -> dict[str, Any]:
    """Convenience function to clean OCR output"""
    cleaner = get_llm_cleaner()
    return cleaner.clean_ocr_text(raw_text, context)
