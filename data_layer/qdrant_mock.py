"""
ERPX AI Accounting - Qdrant Vector DB Mock
==========================================
Mock implementation of Qdrant for:
- Vietnamese accounting laws (Luật kế toán VN)
- Company SOPs (Quy trình nội bộ)
- Historical patterns
"""

import math
import os
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorPoint:
    """A vector point in Qdrant"""

    id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass
class SearchResult:
    """Search result with score"""

    id: str
    score: float
    payload: dict[str, Any]


class QdrantMock:
    """
    Mock Qdrant vector database.
    In production, replace with qdrant_client.
    """

    def __init__(self, url: str = None):
        self.url = url or os.getenv("QDRANT_URL", "mock://localhost:6333")
        self._lock = threading.Lock()

        # Collections storage
        self._collections: dict[str, dict[str, VectorPoint]] = {}

        # Initialize collections
        self._init_collections()

    def _init_collections(self):
        """Initialize mock collections with sample data"""
        # Create collections
        self.create_collection("vn_accounting_laws", vector_size=1024)
        self.create_collection("company_sop", vector_size=1024)
        self.create_collection("historical_patterns", vector_size=1024)

        # Add sample Vietnamese accounting laws
        vn_laws = [
            {
                "id": "law-001",
                "title": "Luật Kế toán 2015",
                "content": "Điều 5. Yêu cầu kế toán: Kế toán phải phản ánh đầy đủ nghiệp vụ kinh tế, tài chính phát sinh vào chứng từ kế toán, sổ kế toán và báo cáo tài chính.",
                "article": "Điều 5",
                "category": "general",
            },
            {
                "id": "law-002",
                "title": "Thông tư 200/2014/TT-BTC",
                "content": "Quy định về chế độ kế toán doanh nghiệp. Tài khoản 133 - Thuế GTGT được khấu trừ: Tài khoản này dùng để phản ánh số thuế GTGT đầu vào được khấu trừ.",
                "article": "Tài khoản 133",
                "category": "vat",
            },
            {
                "id": "law-003",
                "title": "Nghị định 123/2020/NĐ-CP",
                "content": "Quy định về hóa đơn, chứng từ. Hóa đơn điện tử có các nội dung bắt buộc: Tên hóa đơn, ký hiệu mẫu số hóa đơn, ký hiệu hóa đơn, số hóa đơn.",
                "article": "Điều 10",
                "category": "invoice",
            },
            {
                "id": "law-004",
                "title": "Thông tư 78/2021/TT-BTC",
                "content": "Quy định về hóa đơn điện tử. Ký hiệu hóa đơn gồm: Ký tự đầu là số 1 hoặc 2, tiếp theo là một chữ cái và 2 số cuối năm tạo hóa đơn.",
                "article": "Điều 4",
                "category": "e-invoice",
            },
            {
                "id": "law-005",
                "title": "Chuẩn mực kế toán VAS 01",
                "content": "Chuẩn mực chung: Các yêu cầu cơ bản đối với kế toán bao gồm: Trung thực, Khách quan, Đầy đủ, Kịp thời, Dễ hiểu, Có thể so sánh.",
                "article": "VAS 01",
                "category": "standards",
            },
        ]

        for law in vn_laws:
            # Generate mock embedding
            vector = self._mock_embedding(law["content"])
            self.upsert("vn_accounting_laws", law["id"], vector, law)

        # Add sample SOPs
        sops = [
            {
                "id": "sop-001",
                "title": "SOP Phê duyệt hóa đơn",
                "content": "Quy trình phê duyệt: 1. Kiểm tra thông tin hóa đơn (serial, số, ngày). 2. Đối chiếu với đơn hàng. 3. Phê duyệt nếu khớp hoặc chuyển review nếu có sai lệch.",
                "category": "approval",
            },
            {
                "id": "sop-002",
                "title": "SOP Đối chiếu ngân hàng",
                "content": "Đối chiếu hàng ngày: So khớp giao dịch ngân hàng với chứng từ kế toán. Sai lệch chấp nhận: ±0.5% hoặc ±50,000 VND. Ngày chênh lệch tối đa: 7 ngày.",
                "category": "reconciliation",
            },
            {
                "id": "sop-003",
                "title": "SOP Định khoản tự động",
                "content": "Nguyên tắc định khoản: Hóa đơn mua hàng: Nợ 152/156, Có 331. Thuế GTGT đầu vào: Nợ 133, Có 331. Hóa đơn bán hàng: Nợ 131, Có 511/512, Có 33311.",
                "category": "coding",
            },
        ]

        for sop in sops:
            vector = self._mock_embedding(sop["content"])
            self.upsert("company_sop", sop["id"], vector, sop)

    def _mock_embedding(self, text: str, dim: int = 1024) -> list[float]:
        """
        Generate a mock embedding vector.
        In production, use BGE M3 or similar embedding model.
        """
        # Simple hash-based mock embedding
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Extend to desired dimension
        vector = []
        for i in range(dim):
            byte_idx = i % len(hash_bytes)
            # Normalize to [-1, 1]
            val = (hash_bytes[byte_idx] / 255.0) * 2 - 1
            # Add some variation based on position
            val = val * math.cos(i * 0.01)
            vector.append(val)

        # Normalize vector
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(v1) != len(v2):
            return 0.0

        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    # =========================================================================
    # COLLECTION OPERATIONS
    # =========================================================================

    def create_collection(self, name: str, vector_size: int = 1024) -> bool:
        """Create a new collection"""
        with self._lock:
            if name not in self._collections:
                self._collections[name] = {}
                return True
            return False

    def delete_collection(self, name: str) -> bool:
        """Delete a collection"""
        with self._lock:
            if name in self._collections:
                del self._collections[name]
                return True
            return False

    def list_collections(self) -> list[str]:
        """List all collections"""
        return list(self._collections.keys())

    # =========================================================================
    # POINT OPERATIONS
    # =========================================================================

    def upsert(self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]) -> bool:
        """Insert or update a point"""
        with self._lock:
            if collection not in self._collections:
                return False

            self._collections[collection][point_id] = VectorPoint(id=point_id, vector=vector, payload=payload)
            return True

    def delete(self, collection: str, point_id: str) -> bool:
        """Delete a point"""
        with self._lock:
            if collection not in self._collections:
                return False

            if point_id in self._collections[collection]:
                del self._collections[collection][point_id]
                return True
            return False

    def get(self, collection: str, point_id: str) -> VectorPoint | None:
        """Get a point by ID"""
        if collection not in self._collections:
            return None
        return self._collections[collection].get(point_id)

    # =========================================================================
    # SEARCH OPERATIONS
    # =========================================================================

    def search(
        self, collection: str, query_vector: list[float], limit: int = 5, filter_payload: dict[str, Any] = None
    ) -> list[SearchResult]:
        """
        Search for similar vectors.
        Returns top-k results sorted by similarity score.
        """
        if collection not in self._collections:
            return []

        results = []

        for point_id, point in self._collections[collection].items():
            # Apply payload filter
            if filter_payload:
                match = all(point.payload.get(k) == v for k, v in filter_payload.items())
                if not match:
                    continue

            # Calculate similarity
            score = self._cosine_similarity(query_vector, point.vector)
            results.append(SearchResult(id=point_id, score=score, payload=point.payload))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        return results[:limit]

    def search_by_text(
        self, collection: str, query_text: str, limit: int = 5, filter_payload: dict[str, Any] = None
    ) -> list[SearchResult]:
        """
        Search using text query (will be embedded).
        """
        query_vector = self._mock_embedding(query_text)
        return self.search(collection, query_vector, limit, filter_payload)


class KnowledgeBase:
    """
    High-level interface for accounting knowledge retrieval.
    """

    def __init__(self, qdrant: QdrantMock = None):
        self.qdrant = qdrant or QdrantMock()

    def search_laws(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Search Vietnamese accounting laws"""
        results = self.qdrant.search_by_text("vn_accounting_laws", query, limit)
        return [
            {
                "id": r.id,
                "score": round(r.score, 4),
                "title": r.payload.get("title"),
                "content": r.payload.get("content"),
                "article": r.payload.get("article"),
                "category": r.payload.get("category"),
            }
            for r in results
        ]

    def search_sop(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Search company SOPs"""
        results = self.qdrant.search_by_text("company_sop", query, limit)
        return [
            {
                "id": r.id,
                "score": round(r.score, 4),
                "title": r.payload.get("title"),
                "content": r.payload.get("content"),
                "category": r.payload.get("category"),
            }
            for r in results
        ]

    def get_vat_rules(self) -> list[dict[str, Any]]:
        """Get all VAT-related rules"""
        return self.search_laws("thuế GTGT VAT khấu trừ", limit=5)

    def get_invoice_rules(self) -> list[dict[str, Any]]:
        """Get invoice formatting rules"""
        return self.search_laws("hóa đơn điện tử ký hiệu serial", limit=5)

    def add_law(self, law_id: str, title: str, content: str, article: str, category: str) -> bool:
        """Add a new law to knowledge base"""
        vector = self.qdrant._mock_embedding(content)
        return self.qdrant.upsert(
            "vn_accounting_laws",
            law_id,
            vector,
            {"id": law_id, "title": title, "content": content, "article": article, "category": category},
        )

    def add_sop(self, sop_id: str, title: str, content: str, category: str) -> bool:
        """Add a new SOP to knowledge base"""
        vector = self.qdrant._mock_embedding(content)
        return self.qdrant.upsert(
            "company_sop", sop_id, vector, {"id": sop_id, "title": title, "content": content, "category": category}
        )


if __name__ == "__main__":
    # Test Qdrant mock
    kb = KnowledgeBase()

    print("=== Vietnamese Accounting Laws ===")
    results = kb.search_laws("hóa đơn điện tử VAT")
    for r in results:
        print(f"\n[{r['score']:.4f}] {r['title']}")
        print(f"  {r['article']}: {r['content'][:100]}...")

    print("\n=== Company SOPs ===")
    results = kb.search_sop("đối chiếu ngân hàng reconciliation")
    for r in results:
        print(f"\n[{r['score']:.4f}] {r['title']}")
        print(f"  {r['content'][:100]}...")

    print("\n=== VAT Rules ===")
    vat_rules = kb.get_vat_rules()
    for r in vat_rules[:2]:
        print(f"  - {r['title']}")
