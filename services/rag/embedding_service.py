"""
Embedding Service for ERP AI
Uses BGE-M3 (BAAI/bge-m3) for Vietnamese/English document embedding
CPU-only mode
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Force CPU mode
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EmbeddingService")

# Lazy load model
_embedding_model = None


def get_embedding_model():
    """Lazy load BGE-M3 model (CPU mode)"""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading BGE-M3 model (CPU mode)... This may take a minute on first run.")
        from FlagEmbedding import BGEM3FlagModel

        _embedding_model = BGEM3FlagModel(
            "BAAI/bge-m3",
            use_fp16=False,  # CPU doesn't support fp16 well
            device="cpu",
        )
        logger.info("BGE-M3 model loaded successfully")
    return _embedding_model


class EmbeddingService:
    """Embedding service for OCR documents"""

    # BGE-M3 produces 1024-dim dense vectors
    VECTOR_DIM = 1024
    COLLECTION_NAME = "erp_ai_docs"

    def __init__(self, qdrant_host: str = "localhost", qdrant_port: int = 6333):
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

        logger.info("EmbeddingService initialized")
        logger.info(f"  Qdrant: {qdrant_host}:{qdrant_port}")

    def ensure_collection(self):
        """Create collection if not exists"""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.COLLECTION_NAME not in collection_names:
            logger.info(f"Creating collection: {self.COLLECTION_NAME}")
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=qdrant_models.VectorParams(size=self.VECTOR_DIM, distance=qdrant_models.Distance.COSINE),
            )
            logger.info(f"Collection created: {self.COLLECTION_NAME}")
        else:
            logger.info(f"Collection already exists: {self.COLLECTION_NAME}")

    def chunk_text(
        self, text: str, lines_per_chunk: int = 4, min_chunk_size: int = 50, max_chunk_size: int = 500
    ) -> list[str]:
        """
        Simple chunking by lines
        Target: 3-6 lines per chunk for better granularity
        """
        if not text:
            return []

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        if not lines:
            return []

        chunks = []

        # Group lines into chunks of lines_per_chunk
        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i : i + lines_per_chunk]
            chunk_text = "\n".join(chunk_lines)

            # Only add if meets minimum size
            if len(chunk_text) >= min_chunk_size:
                chunks.append(chunk_text)
            elif chunks:
                # Append to previous chunk if too small
                chunks[-1] = chunks[-1] + "\n" + chunk_text
            else:
                # First chunk, keep it even if small
                chunks.append(chunk_text)

        # If no chunks, use whole text
        if not chunks and text.strip():
            chunks = [text.strip()]

        return chunks

    def extract_text_from_ocr_json(self, json_path: str) -> dict[str, Any]:
        """Extract text content from OCR JSON output"""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        # Get main text
        main_text = data.get("text", "")

        # Get blocks text (for better recall)
        blocks = data.get("blocks", [])
        blocks_text = " ".join([b.get("text", "") for b in blocks if b.get("text")])

        # Combine for embedding (main text is primary)
        combined_text = main_text
        if blocks_text and blocks_text != main_text:
            combined_text = f"{main_text}\n\n[Blocks]\n{blocks_text}"

        return {
            "text": combined_text,
            "main_text": main_text,
            "blocks_text": blocks_text,
            "source_file": data.get("source_file", json_path),
            "processed_at": data.get("processed_at", datetime.now().isoformat()),
            "metadata": data.get("metadata", {}),
        }

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed list of texts using BGE-M3"""
        if not texts:
            return np.array([])

        model = get_embedding_model()

        # BGE-M3 returns dict with 'dense_vecs'
        embeddings = model.encode(
            texts, batch_size=8, max_length=512, return_dense=True, return_sparse=False, return_colbert_vecs=False
        )

        # embeddings is a dict with 'dense_vecs' key
        if isinstance(embeddings, dict):
            return embeddings["dense_vecs"]
        return embeddings

    def ingest_ocr_json(self, json_path: str) -> int:
        """
        Ingest OCR JSON file into Qdrant

        Returns: number of points inserted
        """
        json_path = Path(json_path)
        if not json_path.exists():
            logger.error(f"File not found: {json_path}")
            return 0

        logger.info(f"Ingesting: {json_path.name}")

        # Extract text
        doc_data = self.extract_text_from_ocr_json(str(json_path))

        if not doc_data["text"].strip():
            logger.warning(f"No text content in {json_path.name}")
            return 0

        # Chunk the text
        chunks = self.chunk_text(doc_data["text"])
        logger.info(f"  Created {len(chunks)} chunks")

        if not chunks:
            return 0

        # Embed chunks
        logger.info("  Embedding chunks...")
        vectors = self.embed_texts(chunks)

        # Prepare points for Qdrant
        points = []
        doc_id = str(uuid.uuid4())[:8]

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = str(uuid.uuid4())

            payload = {
                "source_file": doc_data["source_file"],
                "processed_at": doc_data["processed_at"],
                "doc_type": "invoice",
                "text_preview": doc_data["main_text"][:200] if doc_data["main_text"] else "",
                "chunk_text": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "doc_id": doc_id,
                "json_file": str(json_path),
            }

            points.append(qdrant_models.PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

        # Upsert to Qdrant
        self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)

        logger.info(f"  Inserted {len(points)} points")
        return len(points)

    def ingest_directory(self, directory: str) -> int:
        """Ingest all JSON files in a directory"""
        directory = Path(directory)
        json_files = list(directory.glob("*.json"))

        if not json_files:
            logger.warning(f"No JSON files found in {directory}")
            return 0

        logger.info(f"Found {len(json_files)} JSON files to ingest")

        total_points = 0
        for json_file in json_files:
            points = self.ingest_ocr_json(str(json_file))
            total_points += points

        logger.info(f"Total points ingested: {total_points}")
        return total_points

    def get_collection_info(self) -> dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "name": self.COLLECTION_NAME,
                "points_count": info.points_count,
                "status": info.status.value if hasattr(info.status, "value") else str(info.status),
            }
        except Exception as e:
            return {"error": str(e)}

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search for similar documents"""
        # Embed query
        query_vector = self.embed_texts([query])[0]

        # Search (qdrant-client 1.x uses query_points)
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME, query=query_vector.tolist(), limit=top_k
        )

        # Format results
        formatted = []
        for hit in results.points:
            formatted.append(
                {
                    "score": hit.score,
                    "source_file": hit.payload.get("source_file", "N/A"),
                    "text_preview": hit.payload.get("text_preview", "")[:100],
                    "chunk_text": hit.payload.get("chunk_text", ""),
                    "chunk_index": hit.payload.get("chunk_index", 0),
                    "doc_type": hit.payload.get("doc_type", "unknown"),
                }
            )

        return formatted


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python embedding_service.py <json_file_or_directory>")
        sys.exit(1)

    path = sys.argv[1]

    # Initialize service
    service = EmbeddingService()
    service.ensure_collection()

    # Process
    path_obj = Path(path)
    if path_obj.is_file():
        points = service.ingest_ocr_json(path)
    elif path_obj.is_dir():
        points = service.ingest_directory(path)
    else:
        print(f"Path not found: {path}")
        sys.exit(1)

    # Print stats
    print("\n" + "=" * 50)
    print("Ingestion Complete")
    print("=" * 50)
    info = service.get_collection_info()
    print(f"Collection: {info.get('name', 'N/A')}")
    print(f"Total points: {info.get('points_count', 0)}")
    print(f"Status: {info.get('status', 'unknown')}")
    print("=" * 50)


if __name__ == "__main__":
    main()
