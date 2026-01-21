"""
ERPX AI Accounting - MinIO Object Storage Mock
==============================================
Mock implementation of MinIO/S3 for:
- Raw document storage
- Processed document storage
- Archive storage
"""

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StoredObject:
    """A stored object in MinIO"""

    key: str
    bucket: str
    content: bytes
    content_type: str
    size: int
    etag: str
    metadata: dict[str, str]
    created_at: str
    last_modified: str


@dataclass
class Bucket:
    """A MinIO bucket"""

    name: str
    created_at: str
    objects: dict[str, StoredObject] = field(default_factory=dict)


class MinIOMock:
    """
    Mock MinIO/S3 object storage.
    In production, replace with minio or boto3.
    """

    def __init__(self, endpoint: str = None, access_key: str = None, secret_key: str = None):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "mock://localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")

        self._lock = threading.Lock()
        self._buckets: dict[str, Bucket] = {}

        # Initialize default buckets
        self._init_buckets()

    def _init_buckets(self):
        """Initialize default buckets"""
        for bucket_name in ["raw-documents", "processed-documents", "archive-documents"]:
            self.create_bucket(bucket_name)

        # Add some sample files
        self._add_sample_files()

    def _add_sample_files(self):
        """Add sample files for testing"""
        # Sample invoice JSON
        sample_invoice = {
            "doc_id": "SAMPLE-001",
            "doc_type": "vat_invoice",
            "invoice_serial": "1C24TAA",
            "invoice_no": "0000001",
            "invoice_date": "20/01/2026",
            "vendor": "Công ty ABC",
            "tax_id": "0102030405",
            "items": [{"description": "Văn phòng phẩm", "quantity": 10, "unit_price": 50000, "amount": 500000}],
            "subtotal": 500000,
            "vat_rate": 10,
            "vat_amount": 50000,
            "grand_total": 550000,
        }

        self.put_object(
            bucket="raw-documents",
            key="samples/invoice_001.json",
            content=json.dumps(sample_invoice, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            metadata={"source": "sample", "tenant_id": "tenant-001"},
        )

        # Sample receipt OCR text
        sample_receipt_ocr = """
        ABC MART
        123 Nguyen Hue, Q.1, TP.HCM
        
        Date: 20/01/2026  Time: 14:30
        Receipt No: R2026012001
        
        --------------------------------
        Milk 1L          x2      50,000
        Bread                    25,000
        Eggs (10pcs)             35,000
        --------------------------------
        SUBTOTAL:              110,000
        VAT (10%):              11,000
        --------------------------------
        TOTAL:                 121,000
        
        Cash:                  150,000
        Change:                 29,000
        
        Thank you for shopping!
        """

        self.put_object(
            bucket="raw-documents",
            key="samples/receipt_001.txt",
            content=sample_receipt_ocr.encode("utf-8"),
            content_type="text/plain",
            metadata={"source": "sample", "tenant_id": "tenant-001", "doc_type": "receipt"},
        )

    def _calculate_etag(self, content: bytes) -> str:
        """Calculate ETag (MD5 hash)"""
        return hashlib.md5(content).hexdigest()

    # =========================================================================
    # BUCKET OPERATIONS
    # =========================================================================

    def create_bucket(self, bucket_name: str) -> bool:
        """Create a new bucket"""
        with self._lock:
            if bucket_name in self._buckets:
                return False

            self._buckets[bucket_name] = Bucket(name=bucket_name, created_at=datetime.utcnow().isoformat())
            return True

    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket (must be empty)"""
        with self._lock:
            if bucket_name not in self._buckets:
                return False

            if self._buckets[bucket_name].objects:
                raise ValueError("Bucket not empty")

            del self._buckets[bucket_name]
            return True

    def list_buckets(self) -> list[dict[str, Any]]:
        """List all buckets"""
        return [{"name": b.name, "created_at": b.created_at} for b in self._buckets.values()]

    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists"""
        return bucket_name in self._buckets

    # =========================================================================
    # OBJECT OPERATIONS
    # =========================================================================

    def put_object(
        self,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] = None,
    ) -> str:
        """Upload an object"""
        with self._lock:
            if bucket not in self._buckets:
                raise ValueError(f"Bucket not found: {bucket}")

            now = datetime.utcnow().isoformat()
            etag = self._calculate_etag(content)

            obj = StoredObject(
                key=key,
                bucket=bucket,
                content=content,
                content_type=content_type,
                size=len(content),
                etag=etag,
                metadata=metadata or {},
                created_at=now,
                last_modified=now,
            )

            self._buckets[bucket].objects[key] = obj
            return etag

    def get_object(self, bucket: str, key: str) -> StoredObject | None:
        """Get an object"""
        if bucket not in self._buckets:
            return None
        return self._buckets[bucket].objects.get(key)

    def get_object_content(self, bucket: str, key: str) -> bytes | None:
        """Get object content"""
        obj = self.get_object(bucket, key)
        return obj.content if obj else None

    def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object"""
        with self._lock:
            if bucket not in self._buckets:
                return False

            if key in self._buckets[bucket].objects:
                del self._buckets[bucket].objects[key]
                return True
            return False

    def list_objects(self, bucket: str, prefix: str = "", limit: int = 1000) -> list[dict[str, Any]]:
        """List objects in bucket"""
        if bucket not in self._buckets:
            return []

        results = []
        for key, obj in self._buckets[bucket].objects.items():
            if key.startswith(prefix):
                results.append(
                    {
                        "key": key,
                        "size": obj.size,
                        "etag": obj.etag,
                        "content_type": obj.content_type,
                        "last_modified": obj.last_modified,
                        "metadata": obj.metadata,
                    }
                )

        return results[:limit]

    def copy_object(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> bool:
        """Copy an object"""
        src_obj = self.get_object(src_bucket, src_key)
        if not src_obj:
            return False

        self.put_object(
            bucket=dst_bucket,
            key=dst_key,
            content=src_obj.content,
            content_type=src_obj.content_type,
            metadata=src_obj.metadata,
        )
        return True

    def move_object(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> bool:
        """Move an object"""
        if self.copy_object(src_bucket, src_key, dst_bucket, dst_key):
            return self.delete_object(src_bucket, src_key)
        return False


class DocumentStorage:
    """
    High-level interface for document storage operations.
    """

    def __init__(self, minio: MinIOMock = None):
        self.minio = minio or MinIOMock()

        # Bucket names
        self.RAW_BUCKET = "raw-documents"
        self.PROCESSED_BUCKET = "processed-documents"
        self.ARCHIVE_BUCKET = "archive-documents"

    def upload_raw_document(
        self, tenant_id: str, doc_id: str, content: bytes, filename: str, content_type: str = None
    ) -> str:
        """Upload a raw document"""
        # Determine content type
        if content_type is None:
            ext = filename.split(".")[-1].lower()
            content_type = {
                "json": "application/json",
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "txt": "text/plain",
            }.get(ext, "application/octet-stream")

        # Create key with tenant prefix
        key = f"{tenant_id}/raw/{doc_id}/{filename}"

        self.minio.put_object(
            bucket=self.RAW_BUCKET,
            key=key,
            content=content,
            content_type=content_type,
            metadata={"tenant_id": tenant_id, "doc_id": doc_id, "original_filename": filename},
        )

        return key

    def save_processed_result(self, tenant_id: str, doc_id: str, result: dict[str, Any]) -> str:
        """Save processed result"""
        key = f"{tenant_id}/processed/{doc_id}/result.json"
        content = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")

        self.minio.put_object(
            bucket=self.PROCESSED_BUCKET,
            key=key,
            content=content,
            content_type="application/json",
            metadata={"tenant_id": tenant_id, "doc_id": doc_id, "processed_at": datetime.utcnow().isoformat()},
        )

        return key

    def get_processed_result(self, tenant_id: str, doc_id: str) -> dict[str, Any] | None:
        """Get processed result"""
        key = f"{tenant_id}/processed/{doc_id}/result.json"
        content = self.minio.get_object_content(self.PROCESSED_BUCKET, key)

        if content:
            return json.loads(content.decode("utf-8"))
        return None

    def archive_document(self, tenant_id: str, doc_id: str) -> bool:
        """Move document to archive"""
        # Move raw
        raw_objs = self.minio.list_objects(self.RAW_BUCKET, prefix=f"{tenant_id}/raw/{doc_id}/")
        for obj in raw_objs:
            new_key = obj["key"].replace("/raw/", "/archive/raw/")
            self.minio.move_object(self.RAW_BUCKET, obj["key"], self.ARCHIVE_BUCKET, new_key)

        # Move processed
        processed_objs = self.minio.list_objects(self.PROCESSED_BUCKET, prefix=f"{tenant_id}/processed/{doc_id}/")
        for obj in processed_objs:
            new_key = obj["key"].replace("/processed/", "/archive/processed/")
            self.minio.move_object(self.PROCESSED_BUCKET, obj["key"], self.ARCHIVE_BUCKET, new_key)

        return True

    def list_tenant_documents(self, tenant_id: str, bucket: str = None) -> list[dict[str, Any]]:
        """List all documents for a tenant"""
        bucket = bucket or self.RAW_BUCKET
        return self.minio.list_objects(bucket, prefix=f"{tenant_id}/")

    def get_document_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        """
        Get presigned URL for document download.
        Mock implementation - in production use MinIO presigned URL.
        """
        return f"{self.minio.endpoint}/{bucket}/{key}?expires={expires}"


if __name__ == "__main__":
    # Test MinIO mock
    storage = DocumentStorage()

    print("=== Buckets ===")
    for bucket in storage.minio.list_buckets():
        print(f"  - {bucket['name']}")

    print("\n=== Raw Documents ===")
    for obj in storage.minio.list_objects("raw-documents"):
        print(f"  {obj['key']} ({obj['size']} bytes)")

    print("\n=== Upload Test ===")
    key = storage.upload_raw_document(
        tenant_id="tenant-001", doc_id="TEST-001", content=b'{"test": true}', filename="test.json"
    )
    print(f"  Uploaded: {key}")

    print("\n=== Save Processed ===")
    result_key = storage.save_processed_result(
        tenant_id="tenant-001",
        doc_id="TEST-001",
        result={"asof_payload": {"doc_type": "receipt"}, "needs_human_review": False},
    )
    print(f"  Saved: {result_key}")

    # Retrieve
    result = storage.get_processed_result("tenant-001", "TEST-001")
    print(f"  Retrieved: {result}")
