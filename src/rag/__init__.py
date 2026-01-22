"""
ERPX AI Accounting - RAG Module (Qdrant + Embeddings)
=====================================================
Vector store for accounting knowledge base retrieval.
"""

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.core import config as core_config

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Use core config QDRANT_URL, fallback to QDRANT_HOST env
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = core_config.QDRANT_URL or f"http://{QDRANT_HOST}:{QDRANT_PORT}"

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "accounting_kb")
EMBEDDING_DIM = 384  # For sentence-transformers/all-MiniLM-L6-v2

# =============================================================================
# Embedding Model
# =============================================================================

_embedding_model = None


def get_embedding_model():
    """Get or create embedding model"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not available")
            _embedding_model = None
    return _embedding_model


def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text"""
    model = get_embedding_model()
    if model is None:
        return None

    try:
        # Truncate very long text
        if len(text) > 8000:
            text = text[:8000]

        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts"""
    model = get_embedding_model()
    if model is None:
        return []

    try:
        # Truncate texts
        texts = [t[:8000] for t in texts]
        embeddings = model.encode(texts)
        return [e.tolist() for e in embeddings]
    except Exception as e:
        logger.error(f"Batch embedding generation failed: {e}")
        return []


# =============================================================================
# Qdrant Client
# =============================================================================


@dataclass
class SearchResult:
    """RAG search result"""

    id: str
    score: float
    text: str
    metadata: dict[str, Any]
    source: str


class QdrantClient:
    """Qdrant vector database client"""

    def __init__(self, url: str = QDRANT_URL):
        self.url = url
        self.client = httpx.Client(timeout=30.0)

    async def health_check(self) -> bool:
        """Check if Qdrant is healthy"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def ensure_collection(self, collection_name: str = COLLECTION_NAME) -> bool:
        """Ensure collection exists, create if not"""
        try:
            # Check if collection exists
            resp = self.client.get(f"{self.url}/collections/{collection_name}")
            if resp.status_code == 200:
                logger.info(f"Collection {collection_name} already exists")
                return True

            # Create collection
            payload = {"vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"}}
            resp = self.client.put(f"{self.url}/collections/{collection_name}", json=payload)

            if resp.status_code in [200, 201]:
                logger.info(f"Collection {collection_name} created")
                return True
            else:
                logger.error(f"Failed to create collection: {resp.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            return False

    def upsert_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        collection_name: str = COLLECTION_NAME,
    ) -> int:
        """
        Upsert documents into Qdrant.
        Returns number of documents upserted.
        """
        if not texts:
            return 0

        # Generate embeddings
        embeddings = generate_embeddings_batch(texts)
        if not embeddings:
            logger.error("Failed to generate embeddings")
            return 0

        # Ensure collection exists
        self.ensure_collection(collection_name)

        # Build points
        points = []
        for i, (text, embedding, metadata) in enumerate(zip(texts, embeddings, metadatas)):
            # Generate ID from text hash
            doc_id = hashlib.md5(text.encode()).hexdigest()

            point = {
                "id": doc_id,
                "vector": embedding,
                "payload": {
                    "text": text,
                    **metadata,
                },
            }
            points.append(point)

        # Batch upsert (max 100 per batch)
        batch_size = 100
        total_upserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]

            try:
                resp = self.client.put(
                    f"{self.url}/collections/{collection_name}/points", json={"points": batch}, params={"wait": "true"}
                )

                if resp.status_code in [200, 201]:
                    total_upserted += len(batch)
                else:
                    logger.error(f"Upsert batch failed: {resp.text}")

            except Exception as e:
                logger.error(f"Upsert batch failed: {e}")

        logger.info(f"Upserted {total_upserted} documents to {collection_name}")
        return total_upserted

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.5,
        filter_dict: dict[str, Any] | None = None,
        collection_name: str = COLLECTION_NAME,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            filter_dict: Metadata filters
            collection_name: Qdrant collection name

        Returns:
            List of SearchResult objects
        """
        # Generate query embedding
        query_embedding = generate_embedding(query)
        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return []

        # Build search request
        search_params = {
            "vector": query_embedding,
            "limit": limit,
            "with_payload": True,
            "score_threshold": score_threshold,
        }

        # Add filter if provided
        if filter_dict:
            search_params["filter"] = {"must": [{"key": k, "match": {"value": v}} for k, v in filter_dict.items()]}

        try:
            resp = self.client.post(f"{self.url}/collections/{collection_name}/points/search", json=search_params)

            if resp.status_code != 200:
                logger.error(f"Search failed: {resp.text}")
                return []

            results = []
            data = resp.json()

            for hit in data.get("result", []):
                payload = hit.get("payload", {})
                result = SearchResult(
                    id=str(hit.get("id", "")),
                    score=hit.get("score", 0.0),
                    text=payload.get("text", ""),
                    metadata={k: v for k, v in payload.items() if k != "text"},
                    source=payload.get("source", "unknown"),
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_collection(self, collection_name: str = COLLECTION_NAME) -> bool:
        """Delete a collection"""
        try:
            resp = self.client.delete(f"{self.url}/collections/{collection_name}")
            return resp.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Delete collection failed: {e}")
            return False

    def get_collection_info(self, collection_name: str = COLLECTION_NAME) -> dict | None:
        """Get collection info"""
        try:
            resp = self.client.get(f"{self.url}/collections/{collection_name}")
            if resp.status_code == 200:
                return resp.json().get("result")
            return None
        except Exception as e:
            logger.error(f"Get collection info failed: {e}")
            return None


# =============================================================================
# RAG Helper Functions
# =============================================================================

# Singleton client
_qdrant_client = None


def get_qdrant_client() -> QdrantClient:
    """Get singleton Qdrant client"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient()
    return _qdrant_client


def ingest_accounting_knowledge(
    documents: list[dict[str, Any]],
    source: str = "manual",
) -> int:
    """
    Ingest accounting knowledge documents.

    Each document should have:
    - text: The content
    - title: Document title
    - category: e.g., "thong_tu", "chuan_muc", "huong_dan"
    - url: Source URL (optional)
    """
    client = get_qdrant_client()

    texts = []
    metadatas = []

    for doc in documents:
        text = doc.get("text", "")
        if not text:
            continue

        # Chunk long documents
        chunks = chunk_text(text, chunk_size=1000, overlap=100)

        for i, chunk in enumerate(chunks):
            texts.append(chunk)
            metadatas.append(
                {
                    "title": doc.get("title", "Untitled"),
                    "category": doc.get("category", "general"),
                    "source": source,
                    "url": doc.get("url", ""),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )

    return client.upsert_documents(texts, metadatas)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to end at sentence boundary
        if end < len(text):
            # Look for sentence ending
            for sep in [". ", ".\n", "! ", "? "]:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size // 2:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def search_accounting_context(
    query: str,
    limit: int = 5,
    category: str | None = None,
) -> list[SearchResult]:
    """
    Search for relevant accounting context.

    Args:
        query: The search query
        limit: Maximum results
        category: Filter by category (thong_tu, chuan_muc, huong_dan)

    Returns:
        List of relevant documents
    """
    client = get_qdrant_client()

    filter_dict = None
    if category:
        filter_dict = {"category": category}

    return client.search(
        query=query,
        limit=limit,
        score_threshold=0.5,
        filter_dict=filter_dict,
    )


def format_context_for_llm(results: list[SearchResult]) -> str:
    """Format search results as context for LLM"""
    if not results:
        return "Không tìm thấy tài liệu tham khảo liên quan."

    context_parts = ["### Tài liệu tham khảo:\n"]

    for i, result in enumerate(results, 1):
        part = f"""
**[{i}] {result.metadata.get("title", "Tài liệu")}**
- Nguồn: {result.source}
- Độ liên quan: {result.score:.2%}
- Nội dung:
{result.text[:500]}{"..." if len(result.text) > 500 else ""}
"""
        context_parts.append(part)

    return "\n".join(context_parts)


# =============================================================================
# TT200 Chart of Accounts Knowledge Base
# =============================================================================

TT200_ACCOUNTS_KB = """
# Hệ thống tài khoản kế toán theo Thông tư 200/2014/TT-BTC

## Loại 1: Tài sản ngắn hạn

### TK 111 - Tiền mặt
- 1111: Tiền Việt Nam
- 1112: Ngoại tệ
- 1113: Vàng bạc, kim khí quý, đá quý

### TK 112 - Tiền gửi ngân hàng
- 1121: Tiền Việt Nam
- 1122: Ngoại tệ
- 1123: Vàng bạc, kim khí quý, đá quý

### TK 131 - Phải thu của khách hàng
Dùng để phản ánh các khoản nợ phải thu và tình hình thanh toán nợ phải thu của doanh nghiệp với khách hàng.

### TK 133 - Thuế GTGT được khấu trừ
- 1331: Thuế GTGT được khấu trừ của hàng hóa, dịch vụ
- 1332: Thuế GTGT được khấu trừ của TSCĐ

### TK 152 - Nguyên liệu, vật liệu
Nguyên liệu chính, vật liệu phụ, nhiên liệu, phụ tùng thay thế, vật liệu khác.

### TK 153 - Công cụ, dụng cụ
- 1531: Công cụ, dụng cụ
- 1532: Bao bì luân chuyển
- 1533: Đồ dùng cho thuê
- 1534: Thiết bị, phụ tùng thay thế

### TK 154 - Chi phí sản xuất, kinh doanh dở dang
Chi phí nguyên vật liệu trực tiếp, nhân công trực tiếp, chi phí sản xuất chung.

### TK 156 - Hàng hóa
- 1561: Giá mua hàng hóa
- 1562: Chi phí thu mua hàng hóa
- 1567: Hàng hóa bất động sản

## Loại 2: Tài sản dài hạn

### TK 211 - Tài sản cố định hữu hình
- 2111: Nhà cửa, vật kiến trúc
- 2112: Máy móc, thiết bị
- 2113: Phương tiện vận tải, truyền dẫn
- 2114: Thiết bị, dụng cụ quản lý
- 2115: Cây lâu năm, súc vật làm việc và cho sản phẩm
- 2118: Tài sản cố định khác

### TK 214 - Hao mòn tài sản cố định
- 2141: Hao mòn TSCĐ hữu hình
- 2142: Hao mòn TSCĐ thuê tài chính
- 2143: Hao mòn TSCĐ vô hình
- 2147: Hao mòn bất động sản đầu tư

## Loại 3: Nợ phải trả

### TK 331 - Phải trả cho người bán
Phản ánh tình hình thanh toán các khoản nợ phải trả cho người bán vật tư, hàng hóa, người cung cấp dịch vụ.

### TK 333 - Thuế và các khoản phải nộp Nhà nước
- 3331: Thuế GTGT phải nộp
  - 33311: Thuế GTGT đầu ra
  - 33312: Thuế GTGT hàng nhập khẩu
- 3332: Thuế tiêu thụ đặc biệt
- 3333: Thuế xuất, nhập khẩu
- 3334: Thuế thu nhập doanh nghiệp
- 3335: Thuế thu nhập cá nhân
- 3336: Thuế tài nguyên
- 3337: Thuế nhà đất, tiền thuê đất
- 3338: Thuế bảo vệ môi trường và các loại thuế khác
- 3339: Phí, lệ phí và các khoản phải nộp khác

### TK 334 - Phải trả người lao động
- 3341: Phải trả công nhân viên
- 3348: Phải trả người lao động khác

### TK 338 - Phải trả, phải nộp khác
- 3381: Tài sản thừa chờ giải quyết
- 3382: Kinh phí công đoàn
- 3383: Bảo hiểm xã hội
- 3384: Bảo hiểm y tế
- 3385: Phải trả về cổ phần hóa
- 3386: Bảo hiểm thất nghiệp
- 3387: Doanh thu chưa thực hiện
- 3388: Phải trả, phải nộp khác

## Loại 4: Vốn chủ sở hữu

### TK 411 - Vốn đầu tư của chủ sở hữu
- 4111: Vốn góp của chủ sở hữu
- 4112: Thặng dư vốn cổ phần
- 4118: Vốn khác

### TK 421 - Lợi nhuận sau thuế chưa phân phối
- 4211: Lợi nhuận sau thuế chưa phân phối năm trước
- 4212: Lợi nhuận sau thuế chưa phân phối năm nay

## Loại 5: Doanh thu

### TK 511 - Doanh thu bán hàng và cung cấp dịch vụ
- 5111: Doanh thu bán hàng hóa
- 5112: Doanh thu bán các thành phẩm
- 5113: Doanh thu cung cấp dịch vụ
- 5114: Doanh thu trợ cấp, trợ giá
- 5117: Doanh thu kinh doanh bất động sản đầu tư
- 5118: Doanh thu khác

### TK 515 - Doanh thu hoạt động tài chính
Lãi tiền gửi, tiền cho vay, lãi từ đầu tư, chênh lệch tỷ giá, cổ tức và lợi nhuận được chia.

## Loại 6: Chi phí sản xuất, kinh doanh

### TK 611 - Mua hàng (Phương pháp kiểm kê định kỳ)

### TK 621 - Chi phí nguyên liệu, vật liệu trực tiếp

### TK 622 - Chi phí nhân công trực tiếp

### TK 623 - Chi phí sử dụng máy thi công

### TK 627 - Chi phí sản xuất chung
- 6271: Chi phí nhân viên phân xưởng
- 6272: Chi phí vật liệu
- 6273: Chi phí dụng cụ sản xuất
- 6274: Chi phí khấu hao TSCĐ
- 6277: Chi phí dịch vụ mua ngoài
- 6278: Chi phí bằng tiền khác

### TK 632 - Giá vốn hàng bán

### TK 635 - Chi phí tài chính
Lãi tiền vay, chiết khấu thanh toán, lỗ tỷ giá, dự phòng đầu tư tài chính.

### TK 641 - Chi phí bán hàng
- 6411: Chi phí nhân viên
- 6412: Chi phí vật liệu, bao bì
- 6413: Chi phí dụng cụ, đồ dùng
- 6414: Chi phí khấu hao TSCĐ
- 6415: Chi phí bảo hành
- 6417: Chi phí dịch vụ mua ngoài
- 6418: Chi phí bằng tiền khác

### TK 642 - Chi phí quản lý doanh nghiệp
- 6421: Chi phí nhân viên quản lý
- 6422: Chi phí vật liệu quản lý
- 6423: Chi phí đồ dùng văn phòng
- 6424: Chi phí khấu hao TSCĐ
- 6425: Thuế, phí và lệ phí
- 6426: Chi phí dự phòng
- 6427: Chi phí dịch vụ mua ngoài
- 6428: Chi phí bằng tiền khác

## Loại 7: Thu nhập khác

### TK 711 - Thu nhập khác
Thu từ thanh lý, nhượng bán TSCĐ, thu tiền phạt vi phạm hợp đồng, thu các khoản nợ khó đòi đã xử lý xóa sổ.

## Loại 8: Chi phí khác

### TK 811 - Chi phí khác
Chi về thanh lý, nhượng bán TSCĐ, tiền phạt vi phạm hợp đồng, chi phí bất thường khác.

### TK 821 - Chi phí thuế thu nhập doanh nghiệp
- 8211: Chi phí thuế TNDN hiện hành
- 8212: Chi phí thuế TNDN hoãn lại

## Loại 9: Xác định kết quả kinh doanh

### TK 911 - Xác định kết quả kinh doanh
Tài khoản này dùng để xác định và phản ánh kết quả hoạt động kinh doanh và các hoạt động khác của doanh nghiệp trong một kỳ kế toán năm.

## Nguyên tắc ghi nhận

1. **Nguyên tắc ghi Nợ/Có:**
   - Tài sản tăng → Ghi Nợ
   - Tài sản giảm → Ghi Có
   - Nguồn vốn tăng → Ghi Có
   - Nguồn vốn giảm → Ghi Nợ
   - Chi phí phát sinh → Ghi Nợ
   - Doanh thu phát sinh → Ghi Có

2. **Cân đối:** Tổng Nợ = Tổng Có trong mọi bút toán

3. **Hóa đơn GTGT đầu vào:**
   - Nợ TK 152/153/156/211: Giá mua chưa thuế
   - Nợ TK 133: Thuế GTGT được khấu trừ
   - Có TK 111/112/331: Tổng thanh toán

4. **Hóa đơn GTGT đầu ra:**
   - Nợ TK 111/112/131: Tổng thanh toán
   - Có TK 511: Doanh thu chưa thuế
   - Có TK 33311: Thuế GTGT đầu ra
"""


def bootstrap_tt200_knowledge() -> int:
    """Bootstrap TT200 chart of accounts knowledge"""
    documents = [
        {
            "text": TT200_ACCOUNTS_KB,
            "title": "Hệ thống tài khoản kế toán Thông tư 200/2014/TT-BTC",
            "category": "thong_tu",
            "url": "https://thuvienphapluat.vn/van-ban/Ke-toan-Kiem-toan/Thong-tu-200-2014-TT-BTC-huong-dan-che-do-ke-toan-doanh-nghiep-263599.aspx",
        }
    ]

    return ingest_accounting_knowledge(documents, source="bootstrap")


__all__ = [
    "QdrantClient",
    "SearchResult",
    "get_qdrant_client",
    "generate_embedding",
    "generate_embeddings_batch",
    "ingest_accounting_knowledge",
    "search_accounting_context",
    "format_context_for_llm",
    "chunk_text",
    "bootstrap_tt200_knowledge",
    "COLLECTION_NAME",
]
