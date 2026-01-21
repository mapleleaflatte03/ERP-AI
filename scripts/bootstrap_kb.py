#!/usr/bin/env python3
"""
ERPX AI - Knowledge Base Bootstrap Script
==========================================
Crawls Vietnamese accounting regulations using Zyte API and ingests into Qdrant.

Collections created:
- tax_laws_vi: Vietnamese tax laws and regulations
- accounting_policies: TT200/133 accounting policies
- company_sop: Standard operating procedures
- documents_ingested: User-uploaded documents (empty initially)
"""

import logging
import os
import sys
import uuid
from datetime import datetime

# Add project root
sys.path.insert(0, "/root/erp-ai")

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Try to import sentence_transformers
try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("Warning: sentence_transformers not available, using mock embeddings")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY", "841f16cf94d54ef081b01bef75ee276d")
ZYTE_API_URL = "https://api.zyte.com/v1/extract"

# Collections to create
COLLECTIONS = {
    "tax_laws_vi": "Vietnamese tax laws, VAT regulations, corporate tax",
    "accounting_policies": "TT200/TT133 accounting standards, chart of accounts",
    "company_sop": "Standard operating procedures for accounting",
    "documents_ingested": "User-uploaded and processed documents",
}

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# =============================================================================
# Knowledge Base Content (Built-in for reliability)
# =============================================================================

TT200_KNOWLEDGE = """
# Thông tư 200/2014/TT-BTC - Hệ thống Tài khoản Kế toán Việt Nam

## Loại 1 - Tài sản ngắn hạn
- 111: Tiền mặt (Cash)
- 112: Tiền gửi ngân hàng (Bank deposits)
- 121: Chứng khoán kinh doanh (Trading securities)
- 131: Phải thu khách hàng (Accounts receivable)
- 133: Thuế GTGT được khấu trừ (VAT deductible)
- 141: Tạm ứng (Advances)
- 151: Hàng mua đang đi đường (Goods in transit)
- 152: Nguyên liệu, vật liệu (Raw materials)
- 153: Công cụ, dụng cụ (Tools and supplies)
- 154: Chi phí SXKD dở dang (Work in progress)
- 155: Thành phẩm (Finished goods)
- 156: Hàng hóa (Merchandise)
- 157: Hàng gửi bán (Goods sent on consignment)

## Loại 2 - Tài sản dài hạn
- 211: Tài sản cố định hữu hình (Tangible fixed assets)
- 212: Tài sản cố định thuê tài chính (Finance lease assets)
- 213: Tài sản cố định vô hình (Intangible assets)
- 214: Hao mòn TSCĐ (Accumulated depreciation)
- 217: Bất động sản đầu tư (Investment property)
- 221: Đầu tư vào công ty con (Investment in subsidiaries)
- 222: Đầu tư vào công ty liên kết (Investment in associates)
- 228: Đầu tư khác (Other investments)
- 241: Xây dựng cơ bản dở dang (Construction in progress)
- 242: Chi phí trả trước dài hạn (Long-term prepaid expenses)
- 244: Ký quỹ, ký cược dài hạn (Long-term deposits)

## Loại 3 - Nợ phải trả
- 311: Vay và nợ thuê tài chính ngắn hạn (Short-term loans)
- 315: Nợ dài hạn đến hạn trả (Current portion of long-term debt)
- 331: Phải trả người bán (Accounts payable)
- 333: Thuế và các khoản phải nộp NN (Tax payables)
  - 3331: Thuế GTGT phải nộp (VAT payable)
  - 3332: Thuế TTĐB (Special consumption tax)
  - 3333: Thuế xuất nhập khẩu (Import/export tax)
  - 3334: Thuế TNDN (Corporate income tax)
  - 3335: Thuế TNCN (Personal income tax)
- 334: Phải trả người lao động (Payroll payable)
- 335: Chi phí phải trả (Accrued expenses)
- 336: Phải trả nội bộ (Intercompany payables)
- 337: Thanh toán theo tiến độ HĐXD (Progress billings)
- 338: Phải trả, phải nộp khác (Other payables)
- 341: Vay và nợ thuê tài chính dài hạn (Long-term loans)

## Loại 4 - Vốn chủ sở hữu
- 411: Vốn đầu tư của chủ sở hữu (Owner's capital)
  - 4111: Vốn góp của chủ sở hữu (Contributed capital)
  - 4112: Thặng dư vốn cổ phần (Share premium)
- 412: Chênh lệch đánh giá lại TS (Asset revaluation)
- 413: Chênh lệch tỷ giá hối đoái (Foreign exchange differences)
- 414: Quỹ đầu tư phát triển (Development fund)
- 417: Quỹ hỗ trợ sắp xếp DN (Enterprise restructuring fund)
- 418: Quỹ khác thuộc VCSH (Other equity funds)
- 419: Cổ phiếu quỹ (Treasury shares)
- 421: Lợi nhuận sau thuế chưa phân phối (Retained earnings)

## Loại 5 - Doanh thu
- 511: Doanh thu bán hàng và cung cấp dịch vụ (Revenue)
  - 5111: Doanh thu bán hàng hóa (Sales of goods)
  - 5112: Doanh thu bán thành phẩm (Sales of products)
  - 5113: Doanh thu cung cấp dịch vụ (Service revenue)
  - 5114: Doanh thu trợ cấp, trợ giá (Subsidies)
- 512: Doanh thu nội bộ (Intercompany revenue)
- 515: Doanh thu hoạt động tài chính (Financial income)
- 521: Các khoản giảm trừ doanh thu (Revenue deductions)

## Loại 6 - Chi phí SXKD
- 611: Mua hàng (Purchases)
- 621: Chi phí nguyên vật liệu trực tiếp (Direct materials)
- 622: Chi phí nhân công trực tiếp (Direct labor)
- 623: Chi phí sử dụng máy thi công (Machine costs)
- 627: Chi phí sản xuất chung (Manufacturing overhead)
- 631: Giá thành sản xuất (Cost of production)
- 632: Giá vốn hàng bán (Cost of goods sold)
- 635: Chi phí tài chính (Financial expenses)
- 641: Chi phí bán hàng (Selling expenses)
- 642: Chi phí quản lý doanh nghiệp (Administrative expenses)

## Loại 7 - Thu nhập khác
- 711: Thu nhập khác (Other income)

## Loại 8 - Chi phí khác
- 811: Chi phí khác (Other expenses)
- 821: Chi phí thuế TNDN (Income tax expense)

## Loại 9 - Xác định KQKD
- 911: Xác định kết quả kinh doanh (Profit/Loss determination)

---

# Nguyên tắc ghi sổ kép (Double-entry principle)

1. Mỗi nghiệp vụ kinh tế phải ghi vào ít nhất 2 tài khoản
2. Tổng số tiền ghi Nợ = Tổng số tiền ghi Có
3. Tài khoản tài sản: Tăng ghi Nợ, Giảm ghi Có
4. Tài khoản nguồn vốn/nợ: Tăng ghi Có, Giảm ghi Nợ
5. Tài khoản doanh thu: Phát sinh ghi Có
6. Tài khoản chi phí: Phát sinh ghi Nợ

---

# Ví dụ bút toán thông dụng

## Mua hàng hóa chưa trả tiền:
Nợ TK 156 (Hàng hóa): Giá mua
Nợ TK 133 (Thuế GTGT đầu vào): 10% VAT
  Có TK 331 (Phải trả NCC): Tổng thanh toán

## Bán hàng thu tiền mặt:
Nợ TK 111 (Tiền mặt): Tổng thu
  Có TK 511 (Doanh thu): Doanh thu
  Có TK 3331 (Thuế GTGT đầu ra): 10% VAT

## Trả lương nhân viên:
Nợ TK 642 (Chi phí QLDN): Chi phí lương
  Có TK 334 (Phải trả NLĐ): Lương phải trả
"""

VAT_REGULATIONS = """
# Quy định về Thuế Giá trị Gia tăng (VAT) tại Việt Nam

## Thuế suất VAT:
- 0%: Hàng xuất khẩu, vận tải quốc tế
- 5%: Nhu yếu phẩm, giáo dục, y tế
- 8%: Thuế suất ưu đãi (2022-2024)
- 10%: Thuế suất thông thường

## Điều kiện khấu trừ VAT đầu vào:
1. Có hóa đơn GTGT hợp lệ
2. Có chứng từ thanh toán không dùng tiền mặt (> 20 triệu đồng)
3. Hàng hóa/dịch vụ sử dụng cho hoạt động sản xuất kinh doanh

## Kê khai thuế:
- Kỳ kê khai: Tháng hoặc Quý
- Hạn nộp: Ngày 20 tháng sau (kê khai tháng)
- Hạn nộp: Ngày cuối tháng đầu quý sau (kê khai quý)

## Hoàn thuế VAT:
- Xuất khẩu >= 8% doanh thu
- Đầu tư mới chưa có doanh thu
- Có số thuế đầu vào > đầu ra liên tục 12 tháng
"""

INVOICE_REGULATIONS = """
# Quy định về Hóa đơn Điện tử tại Việt Nam

## Loại hóa đơn:
1. Hóa đơn GTGT (VAT Invoice)
2. Hóa đơn bán hàng (Sales Invoice)
3. Các loại hóa đơn khác (Other invoices)

## Nội dung bắt buộc:
- Tên, địa chỉ, MST người bán
- Tên, địa chỉ, MST người mua
- Tên hàng hóa, dịch vụ
- Đơn vị tính, số lượng, đơn giá
- Thành tiền, thuế suất, tiền thuế
- Tổng số tiền thanh toán
- Chữ ký số người bán

## Thời điểm lập hóa đơn:
- Bán hàng: Khi giao hàng
- Dịch vụ: Khi hoàn thành
- Xây dựng: Theo nghiệm thu

## Xử lý hóa đơn sai sót:
- Hủy hóa đơn sai
- Lập hóa đơn điều chỉnh
- Lập biên bản điều chỉnh
"""

ACCOUNTING_SOP = """
# Quy trình Kế toán Chuẩn (Standard Operating Procedures)

## 1. Quy trình xử lý Hóa đơn Mua hàng

### Bước 1: Tiếp nhận
- Kiểm tra tính hợp lệ của hóa đơn
- Đối chiếu với đơn đặt hàng
- Xác nhận nhận hàng/dịch vụ

### Bước 2: Phê duyệt
- Trưởng bộ phận kiểm tra
- Kế toán trưởng phê duyệt
- Giám đốc duyệt (nếu > ngưỡng)

### Bước 3: Hạch toán
- Ghi nhận công nợ
- Ghi nhận VAT đầu vào
- Ghi nhận chi phí/tài sản

### Bước 4: Thanh toán
- Lập đề nghị thanh toán
- Phê duyệt thanh toán
- Thực hiện thanh toán
- Ghi nhận thanh toán

## 2. Quy trình Bán hàng

### Bước 1: Tiếp nhận đơn hàng
- Kiểm tra hạn mức công nợ
- Xác nhận tồn kho
- Duyệt đơn hàng

### Bước 2: Xuất hàng
- Lập phiếu xuất kho
- Giao hàng cho khách
- Ký xác nhận nhận hàng

### Bước 3: Lập hóa đơn
- Tạo hóa đơn điện tử
- Gửi hóa đơn cho khách
- Ghi nhận doanh thu & công nợ

### Bước 4: Thu tiền
- Theo dõi công nợ
- Thu tiền khách hàng
- Ghi nhận thanh toán

## 3. Quy trình Đóng sổ Cuối kỳ

### Bước 1: Đối chiếu
- Đối chiếu ngân hàng
- Đối chiếu công nợ
- Đối chiếu kho

### Bước 2: Điều chỉnh
- Trích khấu hao TSCĐ
- Phân bổ chi phí trả trước
- Trích dự phòng

### Bước 3: Kết chuyển
- Kết chuyển doanh thu
- Kết chuyển chi phí
- Xác định kết quả kinh doanh

### Bước 4: Lập báo cáo
- Bảng cân đối kế toán
- Báo cáo kết quả kinh doanh
- Báo cáo lưu chuyển tiền tệ
"""

# =============================================================================
# Embedding Functions
# =============================================================================

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None and EMBEDDINGS_AVAILABLE:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for texts"""
    model = get_embedding_model()
    if model:
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    else:
        # Mock embeddings for testing
        import random

        return [[random.random() for _ in range(EMBEDDING_DIM)] for _ in texts]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks if chunks else [text]


# =============================================================================
# Qdrant Operations
# =============================================================================


def create_collections(client: QdrantClient):
    """Create all required Qdrant collections"""
    for name, description in COLLECTIONS.items():
        try:
            # Check if collection exists
            collections = client.get_collections().collections
            exists = any(c.name == name for c in collections)

            if not exists:
                client.create_collection(
                    collection_name=name, vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                )
                logger.info(f"Created collection: {name}")
            else:
                logger.info(f"Collection exists: {name}")

        except Exception as e:
            logger.error(f"Error creating collection {name}: {e}")


def ingest_content(
    client: QdrantClient, collection: str, content: str, source: str = "builtin", title: str = ""
) -> int:
    """Ingest content into Qdrant collection"""
    chunks = chunk_text(content)
    if not chunks:
        return 0

    embeddings = get_embeddings(chunks)

    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk,
                    "source": source,
                    "title": title,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "ingested_at": datetime.utcnow().isoformat(),
                },
            )
        )

    # Upsert in batches
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=collection, points=batch)

    logger.info(f"Ingested {len(points)} chunks into {collection}")
    return len(points)


# =============================================================================
# Zyte Crawling (Optional Enhancement)
# =============================================================================


def crawl_with_zyte(url: str) -> str | None:
    """Crawl a URL using Zyte API"""
    if not ZYTE_API_KEY:
        logger.warning("Zyte API key not configured")
        return None

    try:
        response = httpx.post(
            ZYTE_API_URL,
            auth=(ZYTE_API_KEY, ""),
            json={
                "url": url,
                "browserHtml": True,
                "javascript": True,
            },
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            html = data.get("browserHtml", "")
            # Simple text extraction (in production, use BeautifulSoup)
            import re

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)
            return text.strip()
        else:
            logger.error(f"Zyte API error: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Zyte crawl error: {e}")
        return None


# =============================================================================
# Main Bootstrap Function
# =============================================================================


def bootstrap_knowledge_base():
    """Bootstrap the knowledge base with accounting content"""
    logger.info("=" * 60)
    logger.info("ERPX AI Knowledge Base Bootstrap")
    logger.info("=" * 60)

    # Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    logger.info(f"Connected to Qdrant: {QDRANT_URL}")

    # Create collections
    logger.info("\n--- Creating Collections ---")
    create_collections(client)

    # Ingest built-in knowledge
    logger.info("\n--- Ingesting Built-in Knowledge ---")

    total_points = 0

    # TT200 Accounting Standards
    points = ingest_content(
        client,
        "accounting_policies",
        TT200_KNOWLEDGE,
        source="TT200/2014/TT-BTC",
        title="Hệ thống Tài khoản Kế toán Việt Nam",
    )
    total_points += points

    # VAT Regulations
    points = ingest_content(
        client, "tax_laws_vi", VAT_REGULATIONS, source="Luật Thuế GTGT", title="Quy định Thuế GTGT Việt Nam"
    )
    total_points += points

    # Invoice Regulations
    points = ingest_content(
        client, "tax_laws_vi", INVOICE_REGULATIONS, source="NĐ 123/2020/NĐ-CP", title="Quy định Hóa đơn Điện tử"
    )
    total_points += points

    # Accounting SOPs
    points = ingest_content(client, "company_sop", ACCOUNTING_SOP, source="ERPX SOP", title="Quy trình Kế toán Chuẩn")
    total_points += points

    # Try Zyte crawl for additional content
    logger.info("\n--- Attempting Zyte Crawl ---")
    zyte_urls = [
        "https://thuvienphapluat.vn/van-ban/Ke-toan-Kiem-toan/Thong-tu-200-2014-TT-BTC-huong-dan-che-do-ke-toan-doanh-nghiep-263599.aspx",
    ]

    for url in zyte_urls:
        content = crawl_with_zyte(url)
        if content:
            points = ingest_content(
                client,
                "accounting_policies",
                content[:10000],  # Limit content
                source=url,
                title="Zyte Crawled Content",
            )
            total_points += points
            logger.info(f"Crawled and ingested: {url}")
        else:
            logger.warning(f"Could not crawl: {url}")

    # Verify collections
    logger.info("\n--- Collection Status ---")
    for name in COLLECTIONS:
        try:
            info = client.get_collection(name)
            count = info.points_count
            logger.info(f"  {name}: {count} points")
        except Exception as e:
            logger.error(f"  {name}: Error - {e}")

    # Test search
    logger.info("\n--- Testing Search ---")
    test_query = "Tài khoản 152 là gì"
    query_embedding = get_embeddings([test_query])[0]

    results = client.query_points(collection_name="accounting_policies", query_vector=query_embedding, limit=3)

    if results:
        logger.info(f"Search for '{test_query}':")
        for i, result in enumerate(results):
            logger.info(f"  {i + 1}. Score: {result.score:.3f}")
            logger.info(f"     Text: {result.payload.get('text', '')[:100]}...")
    else:
        logger.warning("No search results found")

    logger.info("\n" + "=" * 60)
    logger.info(f"Bootstrap complete! Total points ingested: {total_points}")
    logger.info("=" * 60)

    return total_points


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    try:
        total = bootstrap_knowledge_base()
        if total > 0:
            print(f"\n✅ Knowledge base bootstrapped successfully with {total} points")
            sys.exit(0)
        else:
            print("\n❌ No content was ingested")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Bootstrap failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
