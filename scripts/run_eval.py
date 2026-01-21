#!/usr/bin/env python3
"""
ERPX AI - Evaluation Script
===========================
PR-12: Run model/system evaluations with test datasets.

Usage:
    python scripts/run_eval.py --type accuracy --dataset tests/data/eval_invoices.json
    python scripts/run_eval.py --type latency --samples 100
    python scripts/run_eval.py --type e2e --verbose

Environment:
    DATABASE_URL: PostgreSQL connection string
    LLM_API_KEY: DigitalOcean agent API key (optional for cached runs)
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

from src.observability.metrics import (
    add_evaluation_case,
    complete_evaluation_run,
    create_evaluation_run,
    record_latency,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("erpx.eval")


# ===========================================================================
# Database Connection
# ===========================================================================


async def get_db_connection():
    """Get database connection."""
    db_url = os.getenv("DATABASE_URL", "postgresql://erpx:erpx_secret@localhost:5432/erpx")
    db_url = db_url.replace("postgresql://", "")
    parts = db_url.split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    return await asyncpg.connect(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 5432,
        user=user_pass[0],
        password=user_pass[1],
        database=host_db[1],
    )


# ===========================================================================
# Test Datasets
# ===========================================================================


def get_sample_invoices():
    """Get sample invoice test cases."""
    return [
        {
            "name": "purchase_invoice_basic",
            "input": {
                "text": """
                HÓA ĐƠN GIÁ TRỊ GIA TĂNG
                Số: 0001234
                Ngày: 15/03/2024
                Nhà cung cấp: Công ty TNHH ABC
                Tổng tiền hàng: 10.000.000 VND
                Thuế GTGT (10%): 1.000.000 VND
                Tổng thanh toán: 11.000.000 VND
                """,
                "file_type": "image/png",
            },
            "expected": {
                "doc_type": "purchase_invoice",
                "vendor": "Công ty TNHH ABC",
                "invoice_no": "0001234",
                "total_amount": 11000000,
                "vat_amount": 1000000,
                "entries_balanced": True,
            },
        },
        {
            "name": "purchase_invoice_office_supplies",
            "input": {
                "text": """
                HÓA ĐƠN
                Mã HĐ: HD-2024-0567
                Ngày lập: 20/03/2024
                Bên bán: Văn phòng phẩm Thiên Long
                Mặt hàng: Văn phòng phẩm
                Giá trị: 2.500.000 VND
                VAT 10%: 250.000 VND
                Tổng cộng: 2.750.000 VND
                """,
                "file_type": "application/pdf",
            },
            "expected": {
                "doc_type": "purchase_invoice",
                "vendor": "Văn phòng phẩm Thiên Long",
                "invoice_no": "HD-2024-0567",
                "total_amount": 2750000,
                "vat_amount": 250000,
                "entries_balanced": True,
            },
        },
        {
            "name": "sales_invoice",
            "input": {
                "text": """
                HÓA ĐƠN BÁN HÀNG
                Số HĐ: SL-0089
                Ngày: 25/03/2024
                Khách hàng: Công ty XYZ
                Doanh thu: 50.000.000 VND
                Thuế GTGT 10%: 5.000.000 VND
                Tổng thanh toán: 55.000.000 VND
                """,
                "file_type": "image/jpeg",
            },
            "expected": {
                "doc_type": "sales_invoice",
                "invoice_no": "SL-0089",
                "total_amount": 55000000,
                "vat_amount": 5000000,
                "entries_balanced": True,
            },
        },
        {
            "name": "expense_receipt",
            "input": {
                "text": """
                BIÊN LAI CHI TIÊU
                Ngày: 10/03/2024
                Nội dung: Chi phí tiếp khách
                Số tiền: 3.000.000 VND
                Người nhận: Nhà hàng Hương Việt
                """,
                "file_type": "image/png",
            },
            "expected": {
                "doc_type": "expense",
                "total_amount": 3000000,
                "entries_balanced": True,
            },
        },
        {
            "name": "utility_bill",
            "input": {
                "text": """
                HÓA ĐƠN TIỀN ĐIỆN
                Tháng 3/2024
                Khách hàng: Công ty ABC
                Mã KH: PE123456
                Điện tiêu thụ: 5.000 kWh
                Thành tiền: 15.000.000 VND
                Thuế GTGT 10%: 1.500.000 VND
                Tổng cộng: 16.500.000 VND
                """,
                "file_type": "application/pdf",
            },
            "expected": {
                "doc_type": "expense",
                "total_amount": 16500000,
                "vat_amount": 1500000,
                "entries_balanced": True,
            },
        },
    ]


# ===========================================================================
# Evaluation Types
# ===========================================================================


async def run_accuracy_eval(conn, args):
    """Run accuracy evaluation on test dataset."""
    logger.info("Starting accuracy evaluation...")

    # Load test cases
    if args.dataset and Path(args.dataset).exists():
        with open(args.dataset) as f:
            test_cases = json.load(f)
    else:
        test_cases = get_sample_invoices()

    # Create evaluation run
    run_id = await create_evaluation_run(
        conn,
        run_name=f"accuracy_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        run_type="accuracy",
        config={"dataset": args.dataset or "built_in", "cases": len(test_cases)},
        environment=args.env,
    )

    logger.info(f"Created evaluation run: {run_id}")

    # Import LLM client
    from src.llm import get_llm_client

    llm_client = get_llm_client()

    for i, case in enumerate(test_cases):
        logger.info(f"Evaluating case {i + 1}/{len(test_cases)}: {case['name']}")

        start_time = time.time()
        try:
            # Call LLM
            response = llm_client.generate_json(
                prompt=f"Phân tích hóa đơn sau và trả về JSON:\n{case['input']['text']}",
                system="Bạn là chuyên gia kế toán. Trả về JSON với doc_type, vendor, invoice_no, total_amount, vat_amount, entries.",
                temperature=0.2,
                request_id=f"eval-{run_id}-{i}",
            )

            latency_ms = (time.time() - start_time) * 1000

            # Compare with expected
            result = "pass"
            errors = []

            expected = case["expected"]
            if expected.get("doc_type") and response.get("doc_type") != expected["doc_type"]:
                result = "fail"
                errors.append(f"doc_type mismatch: {response.get('doc_type')} != {expected['doc_type']}")

            if expected.get("total_amount"):
                actual_amount = float(response.get("total_amount", 0))
                expected_amount = float(expected["total_amount"])
                if abs(actual_amount - expected_amount) > 100:  # Allow small tolerance
                    result = "fail"
                    errors.append(f"total_amount mismatch: {actual_amount} != {expected_amount}")

            # Add case to run
            await add_evaluation_case(
                conn,
                run_id=run_id,
                case_name=case["name"],
                input_data=case["input"],
                expected_output=expected,
                actual_output=response,
                result=result,
                latency_ms=latency_ms,
                confidence=float(response.get("confidence", 0)),
                error_message="; ".join(errors) if errors else None,
                case_number=i + 1,
            )

            status_icon = "✅" if result == "pass" else "❌"
            logger.info(f"  {status_icon} {case['name']}: {result} ({latency_ms:.0f}ms)")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"  ❌ {case['name']}: error - {e}")

            await add_evaluation_case(
                conn,
                run_id=run_id,
                case_name=case["name"],
                input_data=case["input"],
                expected_output=case["expected"],
                actual_output=None,
                result="error",
                latency_ms=latency_ms,
                error_message=str(e),
                case_number=i + 1,
            )

    # Complete run and get summary
    summary = await complete_evaluation_run(conn, run_id)

    logger.info("=" * 50)
    logger.info("EVALUATION COMPLETE")
    logger.info(f"  Total cases: {summary['total_cases']}")
    logger.info(f"  Passed: {summary['passed_cases']}")
    logger.info(f"  Failed: {summary['failed_cases']}")
    logger.info(f"  Errors: {summary['error_cases']}")
    logger.info(f"  Accuracy: {summary['accuracy'] * 100:.1f}%" if summary["accuracy"] else "  Accuracy: N/A")
    logger.info(
        f"  Avg latency: {summary['avg_latency_ms']:.0f}ms" if summary["avg_latency_ms"] else "  Avg latency: N/A"
    )
    logger.info("=" * 50)

    return summary


async def run_latency_eval(conn, args):
    """Run latency evaluation."""
    logger.info(f"Starting latency evaluation ({args.samples} samples)...")

    run_id = await create_evaluation_run(
        conn,
        run_name=f"latency_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        run_type="latency",
        config={"samples": args.samples},
        environment=args.env,
    )

    from src.llm import get_llm_client

    llm_client = get_llm_client()

    sample_text = """
    HÓA ĐƠN GIÁ TRỊ GIA TĂNG
    Số: TEST-001
    Ngày: 01/01/2024
    Nhà cung cấp: Test Company
    Tổng tiền: 1.000.000 VND
    """

    latencies = []

    for i in range(args.samples):
        start_time = time.time()
        try:
            response = llm_client.generate_json(
                prompt=f"Parse invoice: {sample_text}",
                system="Return JSON with vendor and amount.",
                temperature=0.0,
                request_id=f"latency-{i}",
            )
            latency_ms = (time.time() - start_time) * 1000
            latencies.append(latency_ms)

            await add_evaluation_case(
                conn,
                run_id=run_id,
                case_name=f"latency_sample_{i + 1}",
                input_data={"sample": i + 1},
                expected_output=None,
                actual_output=response,
                result="pass",
                latency_ms=latency_ms,
                case_number=i + 1,
            )

            # Record to metrics
            await record_latency(conn, "llm_latency", latency_ms)

            if args.verbose:
                logger.info(f"  Sample {i + 1}: {latency_ms:.0f}ms")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            await add_evaluation_case(
                conn,
                run_id=run_id,
                case_name=f"latency_sample_{i + 1}",
                input_data={"sample": i + 1},
                expected_output=None,
                actual_output=None,
                result="error",
                latency_ms=latency_ms,
                error_message=str(e),
                case_number=i + 1,
            )

    summary = await complete_evaluation_run(conn, run_id)

    # Compute percentiles
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

    logger.info("=" * 50)
    logger.info("LATENCY EVALUATION COMPLETE")
    logger.info(f"  Samples: {len(latencies)}")
    logger.info(f"  Avg: {sum(latencies) / len(latencies):.0f}ms" if latencies else "  Avg: N/A")
    logger.info(f"  P50: {p50:.0f}ms")
    logger.info(f"  P95: {p95:.0f}ms")
    logger.info(f"  P99: {p99:.0f}ms")
    logger.info("=" * 50)

    return summary


async def run_e2e_eval(conn, args):
    """Run end-to-end evaluation (upload -> extraction -> proposal)."""
    logger.info("Starting E2E evaluation...")

    run_id = await create_evaluation_run(
        conn,
        run_name=f"e2e_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        run_type="end_to_end",
        environment=args.env,
    )

    # For E2E, we test the full API flow
    import httpx

    api_base = os.getenv("API_URL", "http://localhost:8000")

    test_cases = [
        {
            "name": "e2e_upload_png",
            "file": "tests/fixtures/sample_invoice.png",
            "expected_status": "completed",
        },
    ]

    # Check if test file exists, create dummy if not
    for case in test_cases:
        if not Path(case["file"]).exists():
            logger.warning(f"Test file not found: {case['file']}, using dummy")
            case["use_dummy"] = True

    async with httpx.AsyncClient(base_url=api_base, timeout=60.0) as client:
        for i, case in enumerate(test_cases):
            logger.info(f"E2E test {i + 1}: {case['name']}")
            start_time = time.time()

            try:
                # Upload
                if case.get("use_dummy"):
                    # Create minimal PNG file in memory
                    files = {"file": ("test.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")}
                else:
                    files = {"file": open(case["file"], "rb")}

                response = await client.post("/v1/upload", files=files)
                latency_ms = (time.time() - start_time) * 1000

                result = "pass" if response.status_code == 200 else "fail"

                await add_evaluation_case(
                    conn,
                    run_id=run_id,
                    case_name=case["name"],
                    input_data={"file": case["file"]},
                    expected_output={"status": case["expected_status"]},
                    actual_output=response.json() if response.status_code == 200 else {"error": response.text},
                    result=result,
                    latency_ms=latency_ms,
                    case_number=i + 1,
                )

                logger.info(f"  {'✅' if result == 'pass' else '❌'} {case['name']}: {response.status_code}")

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"  ❌ {case['name']}: {e}")

                await add_evaluation_case(
                    conn,
                    run_id=run_id,
                    case_name=case["name"],
                    input_data={"file": case["file"]},
                    expected_output=None,
                    actual_output=None,
                    result="error",
                    latency_ms=latency_ms,
                    error_message=str(e),
                    case_number=i + 1,
                )

    summary = await complete_evaluation_run(conn, run_id)
    logger.info(f"E2E evaluation complete: {summary['passed_cases']}/{summary['total_cases']} passed")

    return summary


# ===========================================================================
# Main
# ===========================================================================


async def main():
    parser = argparse.ArgumentParser(description="ERPX AI Evaluation Script")
    parser.add_argument(
        "--type",
        choices=["accuracy", "latency", "e2e"],
        default="accuracy",
        help="Evaluation type",
    )
    parser.add_argument("--dataset", help="Path to test dataset JSON")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples for latency test")
    parser.add_argument("--env", default="test", help="Environment (test/staging/production)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    conn = await get_db_connection()

    try:
        if args.type == "accuracy":
            await run_accuracy_eval(conn, args)
        elif args.type == "latency":
            await run_latency_eval(conn, args)
        elif args.type == "e2e":
            await run_e2e_eval(conn, args)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
