#!/usr/bin/env python3
"""
Semantic Search Demo for ERP AI
Query Qdrant using BGE-M3 embeddings
"""

import os
import sys

# Force CPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Add project root to path
sys.path.insert(0, "/root/erp-ai")

from services.rag.embedding_service import EmbeddingService


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_qdrant_demo.py <query>")
        print("")
        print("Examples:")
        print('  python query_qdrant_demo.py "Grand Total"')
        print('  python query_qdrant_demo.py "VAT"')
        print('  python query_qdrant_demo.py "Invoice No"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    print("=" * 60)
    print(f'  Semantic Search: "{query}"')
    print("=" * 60)

    # Initialize service
    service = EmbeddingService()

    # Check collection
    info = service.get_collection_info()
    if "error" in info:
        print(f"Error: {info['error']}")
        sys.exit(1)

    print(f"Collection: {info.get('name', 'N/A')}")
    print(f"Total points: {info.get('points_count', 0)}")
    print("-" * 60)

    # Search
    print(f'\nSearching for: "{query}"')
    print("-" * 60)

    results = service.search(query, top_k=5)

    if not results:
        print("No results found.")
        sys.exit(0)

    for i, result in enumerate(results, 1):
        print(f"\n[Result {i}]")
        print(f"  Score: {result['score']:.4f}")
        print(f"  Source: {result['source_file']}")
        print(f"  Doc Type: {result['doc_type']}")
        print(f"  Chunk Index: {result['chunk_index']}")
        print(f"  Text Preview: {result['text_preview'][:80]}...")
        print("  Chunk Text:")
        # Print chunk text with indentation
        chunk_lines = result["chunk_text"].split("\n")
        for line in chunk_lines[:10]:  # Max 10 lines
            print(f"    {line}")
        if len(chunk_lines) > 10:
            print(f"    ... ({len(chunk_lines) - 10} more lines)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
