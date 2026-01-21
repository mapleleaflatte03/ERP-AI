"""
ERPX AI Accounting - Mock Data Generator
========================================
Generates mock documents for testing and benchmarking.
"""

import json
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

# Vietnamese company names
VENDOR_NAMES = [
    "Công ty TNHH Thương mại ABC",
    "Công ty CP Công nghệ XYZ",
    "Công ty TNHH Dịch vụ Sao Mai",
    "Công ty CP Đầu tư Phú Thành",
    "Công ty TNHH MTV Hương Giang",
    "Công ty TNHH Thiết bị Văn phòng Minh Anh",
    "Công ty CP Vật liệu Xây dựng An Phát",
    "Công ty TNHH Thực phẩm Sạch Việt",
    "Công ty CP Phần mềm FPT Software",
    "Công ty TNHH Logistics Bắc Nam",
    "Công ty CP Nhựa Duy Tân",
    "Công ty TNHH May mặc Việt Tiến",
    "Công ty CP Điện tử Samsung Vina",
    "Công ty TNHH Hóa chất Việt Trì",
    "Công ty CP Thép Hòa Phát",
]

PRODUCT_NAMES = [
    ("Máy tính xách tay Dell Latitude", 25_000_000, "cái"),
    ("Màn hình LCD 24 inch", 4_500_000, "cái"),
    ("Bàn phím cơ Logitech", 2_200_000, "cái"),
    ("Chuột không dây", 350_000, "cái"),
    ("Giấy in A4 Double A", 85_000, "ram"),
    ("Mực in HP 85A", 450_000, "hộp"),
    ("Ghế văn phòng cao cấp", 3_500_000, "cái"),
    ("Bàn làm việc 1m2", 2_800_000, "cái"),
    ("Dịch vụ bảo trì CNTT", 15_000_000, "tháng"),
    ("Phần mềm Microsoft Office", 7_500_000, "license"),
    ("Dịch vụ vệ sinh văn phòng", 8_000_000, "tháng"),
    ("Nước uống đóng chai", 25_000, "thùng"),
    ("Cafe hòa tan G7", 180_000, "hộp"),
    ("Văn phòng phẩm các loại", 500_000, "bộ"),
    ("Dịch vụ vận chuyển", 2_500_000, "chuyến"),
]

# Common account codes
EXPENSE_ACCOUNTS = [
    ("6421", "Chi phí văn phòng"),
    ("6422", "Chi phí điện nước"),
    ("6423", "Chi phí thuê văn phòng"),
    ("6424", "Chi phí dịch vụ"),
    ("6425", "Chi phí nhân sự"),
    ("6426", "Chi phí đi lại"),
    ("6427", "Chi phí tiếp khách"),
    ("6428", "Chi phí quảng cáo"),
    ("1561", "Mua hàng hóa"),
    ("1562", "Chi phí mua hàng"),
    ("2111", "Tài sản cố định"),
    ("1531", "Công cụ dụng cụ"),
]

PAYMENT_METHODS = [
    ("cash", "Tiền mặt", "111"),
    ("bank_transfer", "Chuyển khoản", "112"),
    ("credit", "Công nợ", "331"),
]

DOCUMENT_TYPES = [
    "invoice",
    "receipt",
    "bank_statement",
    "expense_report",
]


@dataclass
class GeneratedDocument:
    """A generated mock document"""

    doc_id: str
    doc_type: str
    raw_content: str
    structured_data: dict[str, Any]
    expected_output: dict[str, Any]


class MockDataGenerator:
    """
    Generates mock Vietnamese accounting documents.

    Features:
    - Invoice generation with VAT
    - Receipt generation
    - Bank statement generation
    - Expected output for testing
    """

    def __init__(self, seed: int = None):
        if seed:
            random.seed(seed)

        self.tenant_id = "demo-tenant-001"

    def generate_invoice(self, doc_id: str = None) -> GeneratedDocument:
        """Generate a mock invoice"""
        doc_id = doc_id or f"INV-{str(uuid.uuid4())[:8].upper()}"

        # Vendor info
        vendor = random.choice(VENDOR_NAMES)
        vendor_tax_code = f"{random.randint(1000000000, 9999999999)}"

        # Invoice details
        invoice_date = datetime.now() - timedelta(days=random.randint(1, 30))
        invoice_no = f"HD{invoice_date.strftime('%Y%m%d')}{random.randint(1000, 9999)}"

        # Line items
        num_items = random.randint(1, 5)
        items = []
        subtotal = 0

        for i in range(num_items):
            product, base_price, unit = random.choice(PRODUCT_NAMES)
            qty = random.randint(1, 10)
            unit_price = base_price * (1 + random.uniform(-0.1, 0.1))  # ±10% variation
            amount = round(qty * unit_price)
            subtotal += amount

            items.append(
                {
                    "line_no": i + 1,
                    "description": product,
                    "quantity": qty,
                    "unit": unit,
                    "unit_price": round(unit_price),
                    "amount": amount,
                }
            )

        # VAT
        vat_rate = random.choice([0, 5, 8, 10])
        vat_amount = round(subtotal * vat_rate / 100)
        grand_total = subtotal + vat_amount

        # Payment
        payment_method, payment_desc, payment_account = random.choice(PAYMENT_METHODS)

        # Expected account coding
        expense_account, expense_desc = random.choice(EXPENSE_ACCOUNTS)

        # Generate raw OCR-like text
        raw_content = f"""
HÓA ĐƠN GIÁ TRỊ GIA TĂNG
Số: {invoice_no}
Ngày: {invoice_date.strftime("%d/%m/%Y")}

Đơn vị bán hàng: {vendor}
Mã số thuế: {vendor_tax_code}

STT | Tên hàng hóa, dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền
"""
        for item in items:
            raw_content += f"{item['line_no']}. {item['description']} | {item['unit']} | {item['quantity']} | {item['unit_price']:,.0f} | {item['amount']:,.0f}\n"

        raw_content += f"""
Cộng tiền hàng: {subtotal:,.0f} VND
Thuế suất GTGT: {vat_rate}%
Tiền thuế GTGT: {vat_amount:,.0f} VND
Tổng cộng tiền thanh toán: {grand_total:,.0f} VND

Bằng chữ: {self._number_to_vietnamese(grand_total)}

Hình thức thanh toán: {payment_desc}
"""

        # Structured data
        structured_data = {
            "doc_type": "invoice",
            "invoice_no": invoice_no,
            "invoice_date": invoice_date.strftime("%Y-%m-%d"),
            "vendor_name": vendor,
            "vendor_tax_code": vendor_tax_code,
            "items": items,
            "subtotal": subtotal,
            "vat_rate": vat_rate,
            "vat_amount": vat_amount,
            "grand_total": grand_total,
            "payment_method": payment_method,
            "currency": "VND",
        }

        # Expected output
        expected_output = {
            "doc_id": doc_id,
            "tenant_id": self.tenant_id,
            "asof_payload": {
                "chung_tu": {
                    "so_chung_tu": invoice_no,
                    "ngay_chung_tu": invoice_date.strftime("%Y-%m-%d"),
                    "loai_chung_tu": "HD-GTGT",
                    "ghi_chu": f"Mua hàng từ {vendor}",
                },
                "hoa_don": {
                    "so_hoa_don": invoice_no,
                    "ngay_hoa_don": invoice_date.strftime("%Y-%m-%d"),
                    "nha_cung_cap": vendor,
                    "ma_so_thue_ncc": vendor_tax_code,
                },
                "thue": {"thue_suat_vat": vat_rate, "tien_thue_vat": vat_amount, "co_hoa_don_hop_le": True},
                "chi_tiet": [
                    {
                        "tai_khoan_no": expense_account,
                        "tai_khoan_co": payment_account,
                        "so_tien": subtotal,
                        "dien_giai": f"Mua hàng - {items[0]['description']}",
                    }
                ],
            },
            "reconciliation_result": None,
            "needs_human_review": grand_total > 100_000_000,  # > 100M needs review
            "review_reasons": ["amount_threshold"] if grand_total > 100_000_000 else [],
            "confidence_score": 0.92,
            "evidence": {
                "key_text_snippets": [
                    f"Tổng cộng tiền thanh toán: {grand_total:,.0f} VND",
                    f"Thuế suất GTGT: {vat_rate}%",
                ],
                "numbers_found": [
                    {"label": "grand_total", "value": grand_total, "source": "ocr"},
                    {"label": "vat_rate", "value": vat_rate, "source": "ocr"},
                ],
            },
        }

        return GeneratedDocument(
            doc_id=doc_id,
            doc_type="invoice",
            raw_content=raw_content,
            structured_data=structured_data,
            expected_output=expected_output,
        )

    def generate_receipt(self, doc_id: str = None) -> GeneratedDocument:
        """Generate a mock receipt"""
        doc_id = doc_id or f"REC-{str(uuid.uuid4())[:8].upper()}"

        vendor = random.choice(VENDOR_NAMES[:8])  # Simpler vendors for receipts
        receipt_date = datetime.now() - timedelta(days=random.randint(1, 15))
        receipt_no = f"PT{receipt_date.strftime('%Y%m%d')}{random.randint(100, 999)}"

        # Single item or simple description
        product, base_price, unit = random.choice(PRODUCT_NAMES[4:])  # Lower value items
        qty = random.randint(1, 5)
        amount = round(qty * base_price * (1 + random.uniform(-0.1, 0.1)))

        # Receipt OCR
        raw_content = f"""
PHIẾU THU
Số: {receipt_no}
Ngày: {receipt_date.strftime("%d/%m/%Y")}

Nội dung: Mua {product}
Số lượng: {qty} {unit}
Đơn giá: {base_price:,.0f} VND

Tổng tiền: {amount:,.0f} VND

Người bán: {vendor}

Đã nhận đủ tiền.
"""

        structured_data = {
            "doc_type": "receipt",
            "receipt_no": receipt_no,
            "receipt_date": receipt_date.strftime("%Y-%m-%d"),
            "vendor_name": vendor,
            "description": f"Mua {product}",
            "amount": amount,
            "currency": "VND",
        }

        expected_output = {
            "doc_id": doc_id,
            "tenant_id": self.tenant_id,
            "asof_payload": {
                "chung_tu": {
                    "so_chung_tu": receipt_no,
                    "ngay_chung_tu": receipt_date.strftime("%Y-%m-%d"),
                    "loai_chung_tu": "PT",
                    "ghi_chu": f"Mua {product}",
                },
                "hoa_don": None,
                "thue": None,
                "chi_tiet": [
                    {"tai_khoan_no": "6421", "tai_khoan_co": "111", "so_tien": amount, "dien_giai": f"Mua {product}"}
                ],
            },
            "reconciliation_result": None,
            "needs_human_review": False,
            "review_reasons": [],
            "confidence_score": 0.88,
            "evidence": {
                "key_text_snippets": [f"Tổng tiền: {amount:,.0f} VND"],
                "numbers_found": [{"label": "amount", "value": amount, "source": "ocr"}],
            },
        }

        return GeneratedDocument(
            doc_id=doc_id,
            doc_type="receipt",
            raw_content=raw_content,
            structured_data=structured_data,
            expected_output=expected_output,
        )

    def generate_bank_statement(self, doc_id: str = None, num_transactions: int = None) -> GeneratedDocument:
        """Generate a mock bank statement"""
        doc_id = doc_id or f"BS-{str(uuid.uuid4())[:8].upper()}"
        num_transactions = num_transactions or random.randint(5, 15)

        statement_date = datetime.now() - timedelta(days=random.randint(1, 10))
        account_no = f"10201234567{random.randint(10, 99)}"
        bank_name = random.choice(["Vietcombank", "BIDV", "Techcombank", "VPBank", "ACB"])

        transactions = []
        balance = random.randint(50_000_000, 500_000_000)

        for i in range(num_transactions):
            txn_date = statement_date - timedelta(days=random.randint(0, 30))
            txn_type = random.choice(["credit", "debit"])

            if txn_type == "credit":
                amount = random.randint(1_000_000, 50_000_000)
                description = random.choice(
                    [
                        f"TT từ KH {random.choice(VENDOR_NAMES)}",
                        f"CK từ công ty {random.choice(VENDOR_NAMES[:5])}",
                        "Thu hồi công nợ",
                    ]
                )
            else:
                amount = random.randint(500_000, 30_000_000)
                description = random.choice(
                    [
                        f"TT cho {random.choice(VENDOR_NAMES)}",
                        f"Chi phí {random.choice(['điện', 'nước', 'thuê nhà', 'internet'])}",
                        f"Thanh toán HD {random.randint(100000, 999999)}",
                    ]
                )

            transactions.append(
                {
                    "date": txn_date.strftime("%Y-%m-%d"),
                    "type": txn_type,
                    "amount": amount,
                    "description": description,
                    "reference": f"FT{txn_date.strftime('%Y%m%d')}{random.randint(100000, 999999)}",
                }
            )

        # Sort by date
        transactions.sort(key=lambda x: x["date"], reverse=True)

        raw_content = f"""
SÀO KÊ TÀI KHOẢN
Ngân hàng: {bank_name}
Số tài khoản: {account_no}
Ngày sao kê: {statement_date.strftime("%d/%m/%Y")}
Số dư hiện tại: {balance:,.0f} VND

LỊCH SỬ GIAO DỊCH
Ngày | Loại | Số tiền | Nội dung | Mã GD
"""
        for txn in transactions:
            txn_type_vn = "Thu" if txn["type"] == "credit" else "Chi"
            raw_content += (
                f"{txn['date']} | {txn_type_vn} | {txn['amount']:,.0f} | {txn['description']} | {txn['reference']}\n"
            )

        structured_data = {
            "doc_type": "bank_statement",
            "bank_name": bank_name,
            "account_no": account_no,
            "statement_date": statement_date.strftime("%Y-%m-%d"),
            "balance": balance,
            "transactions": transactions,
            "currency": "VND",
        }

        expected_output = {
            "doc_id": doc_id,
            "tenant_id": self.tenant_id,
            "asof_payload": None,  # Bank statements don't create accounting entries directly
            "reconciliation_result": {
                "status": "pending",
                "total_transactions": len(transactions),
                "matched": 0,
                "unmatched": len(transactions),
            },
            "needs_human_review": True,
            "review_reasons": ["bank_reconciliation"],
            "confidence_score": 1.0,
            "evidence": {
                "key_text_snippets": [f"Số dư hiện tại: {balance:,.0f} VND"],
                "numbers_found": [{"label": "balance", "value": balance, "source": "structured"}],
            },
        }

        return GeneratedDocument(
            doc_id=doc_id,
            doc_type="bank_statement",
            raw_content=raw_content,
            structured_data=structured_data,
            expected_output=expected_output,
        )

    def generate_expense_report(self, doc_id: str = None) -> GeneratedDocument:
        """Generate a mock expense report"""
        doc_id = doc_id or f"EXP-{str(uuid.uuid4())[:8].upper()}"

        employee_names = ["Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Cường", "Phạm Thị Dung", "Hoàng Văn Em"]
        employee = random.choice(employee_names)
        report_date = datetime.now() - timedelta(days=random.randint(1, 7))

        # Expense items
        expense_types = [
            ("Di chuyển - Taxi", random.randint(100_000, 500_000)),
            ("Ăn uống tiếp khách", random.randint(200_000, 2_000_000)),
            ("Khách sạn", random.randint(500_000, 2_000_000)),
            ("Vé máy bay", random.randint(1_000_000, 5_000_000)),
            ("Chi phí hội nghị", random.randint(500_000, 3_000_000)),
        ]

        selected_expenses = random.sample(expense_types, k=random.randint(2, 4))
        total = sum(e[1] for e in selected_expenses)

        raw_content = f"""
BÁO CÁO CHI PHÍ
Ngày: {report_date.strftime("%d/%m/%Y")}
Nhân viên: {employee}

CHI TIẾT CHI PHÍ
"""
        for i, (desc, amount) in enumerate(selected_expenses, 1):
            raw_content += f"{i}. {desc}: {amount:,.0f} VND\n"

        raw_content += f"""
Tổng chi phí: {total:,.0f} VND

Cam kết: Các chi phí trên là hợp lệ và có chứng từ kèm theo.
Ký tên: {employee}
"""

        structured_data = {
            "doc_type": "expense_report",
            "report_date": report_date.strftime("%Y-%m-%d"),
            "employee": employee,
            "expenses": [{"description": desc, "amount": amount} for desc, amount in selected_expenses],
            "total": total,
            "currency": "VND",
        }

        expected_output = {
            "doc_id": doc_id,
            "tenant_id": self.tenant_id,
            "asof_payload": {
                "chung_tu": {
                    "so_chung_tu": f"BC-CP-{report_date.strftime('%Y%m%d')}",
                    "ngay_chung_tu": report_date.strftime("%Y-%m-%d"),
                    "loai_chung_tu": "BC-CP",
                    "ghi_chu": f"Báo cáo chi phí - {employee}",
                },
                "hoa_don": None,
                "thue": None,
                "chi_tiet": [
                    {
                        "tai_khoan_no": "6426",  # Chi phí đi lại
                        "tai_khoan_co": "141",  # Tạm ứng
                        "so_tien": total,
                        "dien_giai": f"Hoàn ứng chi phí - {employee}",
                    }
                ],
            },
            "reconciliation_result": None,
            "needs_human_review": total > 5_000_000,
            "review_reasons": ["amount_threshold"] if total > 5_000_000 else [],
            "confidence_score": 0.85,
            "evidence": {
                "key_text_snippets": [f"Tổng chi phí: {total:,.0f} VND"],
                "numbers_found": [{"label": "total", "value": total, "source": "ocr"}],
            },
        }

        return GeneratedDocument(
            doc_id=doc_id,
            doc_type="expense_report",
            raw_content=raw_content,
            structured_data=structured_data,
            expected_output=expected_output,
        )

    def generate_batch(self, count: int = 20, doc_types: list[str] = None) -> list[GeneratedDocument]:
        """
        Generate a batch of mock documents.

        Args:
            count: Number of documents to generate
            doc_types: List of document types to generate. If None, use all types.

        Returns:
            List of generated documents
        """
        doc_types = doc_types or DOCUMENT_TYPES
        documents = []

        generators = {
            "invoice": self.generate_invoice,
            "receipt": self.generate_receipt,
            "bank_statement": self.generate_bank_statement,
            "expense_report": self.generate_expense_report,
        }

        for i in range(count):
            doc_type = random.choice(doc_types)
            if doc_type in generators:
                doc = generators[doc_type]()
                documents.append(doc)

        return documents

    def save_batch(self, documents: list[GeneratedDocument], output_dir: str = "data/mock_documents"):
        """Save generated documents to files"""
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "structured"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "expected"), exist_ok=True)

        manifest = []

        for doc in documents:
            # Save raw content
            raw_path = os.path.join(output_dir, "raw", f"{doc.doc_id}.txt")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(doc.raw_content)

            # Save structured data
            structured_path = os.path.join(output_dir, "structured", f"{doc.doc_id}.json")
            with open(structured_path, "w", encoding="utf-8") as f:
                json.dump(doc.structured_data, f, ensure_ascii=False, indent=2)

            # Save expected output
            expected_path = os.path.join(output_dir, "expected", f"{doc.doc_id}.json")
            with open(expected_path, "w", encoding="utf-8") as f:
                json.dump(doc.expected_output, f, ensure_ascii=False, indent=2)

            manifest.append(
                {
                    "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type,
                    "raw_path": f"raw/{doc.doc_id}.txt",
                    "structured_path": f"structured/{doc.doc_id}.json",
                    "expected_path": f"expected/{doc.doc_id}.json",
                }
            )

        # Save manifest
        manifest_path = os.path.join(output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "total_documents": len(documents),
                    "documents": manifest,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return manifest_path

    def _number_to_vietnamese(self, number: int) -> str:
        """Convert number to Vietnamese text (simplified)"""
        if number >= 1_000_000_000:
            return f"{number // 1_000_000_000} tỷ {(number % 1_000_000_000) // 1_000_000} triệu đồng"
        elif number >= 1_000_000:
            return f"{number // 1_000_000} triệu {(number % 1_000_000) // 1000} nghìn đồng"
        elif number >= 1000:
            return f"{number // 1000} nghìn đồng"
        else:
            return f"{number} đồng"


def generate_benchmark_dataset(output_dir: str = "data/benchmark", num_docs: int = 100):
    """Generate a benchmark dataset for testing"""
    generator = MockDataGenerator(seed=42)

    # Generate documents
    documents = generator.generate_batch(count=num_docs)

    # Save
    manifest_path = generator.save_batch(documents, output_dir)

    # Statistics
    by_type = {}
    for doc in documents:
        if doc.doc_type not in by_type:
            by_type[doc.doc_type] = 0
        by_type[doc.doc_type] += 1

    print(f"Generated {len(documents)} documents:")
    for doc_type, count in by_type.items():
        print(f"  - {doc_type}: {count}")
    print(f"Manifest: {manifest_path}")

    return documents


if __name__ == "__main__":
    # Generate benchmark dataset
    print("Generating benchmark dataset...")
    documents = generate_benchmark_dataset(output_dir="data/mock_documents", num_docs=50)

    print("\nSample invoice content:")
    for doc in documents:
        if doc.doc_type == "invoice":
            print(doc.raw_content[:500])
            break
