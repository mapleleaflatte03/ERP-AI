# Kaggle Pilot Summary Report
## ERPX AI Accounting - Data Loader & Adapter Engineer

**Report Date:** 2026-01-20  
**Engineer:** AI Agent (Kaggle Data Loader Role)  
**Status:** ✅ COMPLETE

---

## Executive Summary

Successfully downloaded 3 Kaggle datasets (3.7GB total) and built dataset adapters to convert receipt/invoice images to ERPX RAW/Staging format. Smoke test on 20 SROIE documents achieved **100% OCR success rate**.

---

## 1. Task Completion Matrix

| Task | Status | Details |
|------|--------|---------|
| Task 0: Verify no prior downloads | ✅ | `data/kaggle/` was empty |
| Task 1: Install & configure Kaggle CLI | ✅ | v1.7.4.5, credentials from env vars |
| Task 2: Download datasets | ✅ | 3 datasets, 3.7GB total |
| Task 3: Build Dataset Adapters | ✅ | SROIE + Vietnamese adapters |
| Task 4: Smoke test 20 docs | ✅ | 100% OCR success |
| Task 5: Generate deliverables report | ✅ | This file |

---

## 2. Datasets Downloaded

### 2.1 SROIE (ICDAR 2019)
- **Kaggle slug:** `urbikn/sroie-datasetv2`
- **Size:** 977 MB
- **Images:** 973 (626 train + 347 test)
- **Labels:** company, date, address, total
- **Format:** JPG images + JSON entity labels + OCR bounding boxes
- **Location:** `data/kaggle/sroie-datasetv2/`

### 2.2 Vietnamese Receipts (MC_OCR 2021)
- **Kaggle slug:** `domixi1989/vietnamese-receipts-mc-ocr-2021`
- **Size:** 2.3 GB
- **Images:** 54,402
- **Labels:** SELLER, ADDRESS, TIMESTAMP, TOTAL_COST
- **Format:** CSV metadata with polygons + JPG images
- **Location:** `data/kaggle/vietnamese-receipts/`

### 2.3 PaySim Financial Transactions
- **Kaggle slug:** `ealaxi/paysim1`
- **Size:** 471 MB
- **Records:** 6,362,620 transactions
- **Format:** CSV with step, type, amount, nameOrig, etc.
- **Location:** `data/kaggle/paysim1/`

---

## 3. Dataset Adapters

### 3.1 SROIE Adapter
**File:** `scripts/adapters/kaggle_sroie_to_raw.py`

**Features:**
- Parses JSON entity files (company, date, address, total)
- Extracts OCR text from bounding box coordinate files
- Maps labels to ASOFT-T format:
  - `company` → `seller_name`
  - `date` → `invoice_date`
  - `address` → `address`
  - `total` → `total_amount`
- Copies images to `raw_files/` directory
- Generates `raw_meta.jsonl` with structured metadata

**Usage:**
```bash
python scripts/adapters/kaggle_sroie_to_raw.py --max-docs 50
```

**Output Format (raw_meta.jsonl):**
```json
{
  "doc_id": "sroie_X00016469612",
  "source": "kaggle/sroie-datasetv2",
  "file_path": "raw_files/X00016469612.jpg",
  "doc_type_guess": "receipt",
  "split": "train",
  "ocr_text": "BOOK TA .K (TAMAN DAYA) SDN BHD...",
  "labels": {
    "seller_name": "BOOK TA .K (TAMAN DAYA) SDN BHD",
    "invoice_date": "25/12/2018",
    "address": "NO.53 55,57 & 59, JALAN SAGU 18...",
    "total_amount": "9.00"
  }
}
```

### 3.2 Vietnamese Receipts Adapter
**File:** `scripts/adapters/kaggle_vn_receipts_to_raw.py`

**Features:**
- Parses `mcocr_train_df.csv` metadata
- Maps MC_OCR category labels:
  - `SELLER` (15) → `seller_name`
  - `ADDRESS` (16) → `address`
  - `TIMESTAMP` (17) → `invoice_date`
  - `TOTAL_COST` (18) → `total_amount`
- Locates images across multiple subdirectories
- Includes image quality scores from annotations

**Usage:**
```bash
python scripts/adapters/kaggle_vn_receipts_to_raw.py --max-docs 30
```

---

## 4. Smoke Test Results

### 4.1 Test Configuration
- **Dataset:** SROIE
- **Documents:** 20
- **Pipeline:** OCR (PaddleOCR) → Invoice JSON

### 4.2 Metrics

| Metric | Value |
|--------|-------|
| Documents Processed | 20 |
| OCR Success | 20 (100.0%) |
| OCR Failed | 0 |
| Documents with Labels | 20 |
| Average Text Length | 641 chars |
| Total Text Extracted | 12,826 chars |

### 4.3 Sample Document Analysis

| Doc ID | Text Length | Labels |
|--------|-------------|--------|
| sroie_X00016469612 | 440 | seller_name, date, address, total |
| sroie_X00016469619 | 530 | seller_name, date, address, total |
| sroie_X00016469620 | 680 | seller_name, date, address, total |
| sroie_X51005268472 | 984 | seller_name, date, address, total |

### 4.4 Output Location
```
/root/erp-ai/data/processed/pilot_run_20260120_070452/
├── ocr_results/
├── pilot_summary.json
├── sroie_X00016469612.json
├── sroie_X00016469619.json
└── ... (20 invoice JSON files)
```

---

## 5. ASOFT-T Field Mapping Status

| ASOFT-T Field | SROIE | Vietnamese | PaySim |
|---------------|-------|------------|--------|
| serial | ❌ N/A | ❌ N/A | ❌ N/A |
| invoice_number | ❌ N/A | ❌ N/A | ❌ N/A |
| invoice_date | ✅ date | ✅ TIMESTAMP | ❌ N/A |
| invoice_type | ⚠️ receipt | ⚠️ receipt | ❌ N/A |
| tax_account | ❌ N/A | ❌ N/A | ❌ N/A |
| tax_group | ❌ N/A | ❌ N/A | ❌ N/A |
| line_items | ❌ N/A | ❌ N/A | ❌ N/A |
| seller_name | ✅ company | ✅ SELLER | ❌ N/A |
| address | ✅ address | ✅ ADDRESS | ❌ N/A |
| total_amount | ✅ total | ✅ TOTAL_COST | ✅ amount |

**Note:** SROIE and Vietnamese receipts are retail receipts, not formal tax invoices. They lack invoice serial numbers, tax accounts, and VAT breakdowns typically required for ASOFT-T accounting entries.

---

## 6. Deliverables Checklist

| Deliverable | Location | Status |
|-------------|----------|--------|
| Kaggle datasets | `data/kaggle/<dataset>/` | ✅ |
| Dataset manifests | `data/kaggle/<dataset>/MANIFEST.txt` | ✅ |
| SROIE adapter | `scripts/adapters/kaggle_sroie_to_raw.py` | ✅ |
| Vietnamese adapter | `scripts/adapters/kaggle_vn_receipts_to_raw.py` | ✅ |
| SROIE raw data | `data/raw_kaggle/sroie/raw_meta.jsonl` | ✅ |
| Vietnamese raw data | `data/raw_kaggle/vietnamese_receipts/raw_meta.jsonl` | ✅ |
| Pilot run output | `data/processed/pilot_run_20260120_070452/` | ✅ |
| Pilot test script | `scripts/kaggle_pilot_smoke_test.py` | ✅ |
| Per-test report | `reports/kaggle_pilot_sroie_20260120_070452.md` | ✅ |
| This summary | `reports/kaggle_pilot_summary.md` | ✅ |

---

## 7. Recommendations

### 7.1 For Production Use
1. **Formal Invoice Data:** SROIE/Vietnamese receipts are retail receipts, not formal invoices. For ASOFT-T compliance, obtain datasets with:
   - Invoice serial numbers (Số hóa đơn)
   - VAT breakdowns (10% VAT typical in Vietnam)
   - Tax registration numbers

2. **Vietnamese Invoice Datasets:** Consider:
   - VinAI datasets
   - Vietnamese e-invoice XML samples
   - Real anonymized ASOFT-T exports

### 7.2 For Development
1. **Extend adapters** to handle:
   - PDF multi-page invoices
   - XML/JSON structured invoice formats
   - Batch processing with progress tracking

2. **Add validation** for:
   - Label completeness scoring
   - OCR confidence thresholds
   - Duplicate detection

---

## 8. Disk Usage Summary

```
Dataset                    Size      Items
───────────────────────────────────────────
sroie-datasetv2           977 MB    973 images
vietnamese-receipts       2.3 GB    54,402 images
paysim1                   471 MB    6.36M records
───────────────────────────────────────────
TOTAL                     3.7 GB
```

---

## Appendix: Sample Invoice JSON

```json
{
  "doc_id": "sroie_X00016469612",
  "source": "kaggle/sroie-datasetv2",
  "source_file": "raw_files/X00016469612.jpg",
  "doc_type": "receipt",
  "text": "BOOK TA.K(TAMAN DAYASDN BHD\n789417-W\nNO.55557&59,JALANSAGU18...",
  "invoice_data": {
    "invoice_no": null,
    "date": "25/12/2018",
    "partner_name": "BOOK TA .K (TAMAN DAYA) SDN BHD",
    "total": 9.0,
    "vat": null,
    "grand_total": 9.0,
    "vat_rate": null,
    "doc_type": "receipt",
    "items": []
  },
  "labels": {
    "seller_name": "BOOK TA .K (TAMAN DAYA) SDN BHD",
    "invoice_date": "25/12/2018",
    "address": "NO.53 55,57 & 59, JALAN SAGU 18, TAMAN DAYA, 81100 JOHOR BAHRU, JOHOR.",
    "total_amount": "9.00"
  },
  "processed_at": "2026-01-20T07:04:55.123456"
}
```

---

*End of Report*
