import asyncio
import unittest
from unittest.mock import MagicMock, patch

from src.orchestrator.pipeline import PipelineState, node_extract_document, node_retrieve_context


class TestPipelineAsync(unittest.IsolatedAsyncioTestCase):
    async def test_node_extract_document_async(self):
        # Setup state
        state: PipelineState = {
            "job_id": "test-job",
            "document_key": "test.pdf",
            "status": "processing",
            "timestamps": {},
            "extracted_text": "",
            "key_fields": {},
            "tables": [],
        }

        # Mock dependencies
        with (
            patch("src.storage.download_document") as mock_download,
            patch("src.processing.process_document") as mock_process,
            patch("src.core.config.MINIO_BUCKET", "test-bucket"),
        ):
            # download_document is sync
            mock_download.return_value = b"fake-pdf-content"

            # process_document is sync
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.document_text = "Extracted Text"
            mock_result.key_fields = {"invoice_number": "123"}
            mock_result.tables = []
            mock_process.return_value = mock_result

            # Run the async node
            new_state = await node_extract_document(state)

            # Assertions
            self.assertEqual(new_state["extracted_text"], "Extracted Text")
            self.assertEqual(new_state["key_fields"]["invoice_number"], "123")

            # Verify download_document called with bucket
            mock_download.assert_called_once_with("test-bucket", "test.pdf")

            # Verify process_document called
            mock_process.assert_called_once()

    async def test_node_retrieve_context_async(self):
        # Setup state
        state: PipelineState = {
            "job_id": "test-job",
            "document_key": "test.pdf",
            "status": "processing",
            "timestamps": {},
            "extracted_text": "Extracted Text",
            "key_fields": {"vendor_name": "ABC Corp"},
            "tables": [],
            "rag_context": "",
            "rag_sources": [],
        }

        with patch("src.rag.search_accounting_context") as mock_search:
            # Mock return value
            mock_result = MagicMock()
            mock_result.source = "Test Source"
            mock_result.text = "Context Text"
            mock_result.metadata = {"title": "Doc Title"}
            mock_result.score = 0.9
            mock_search.return_value = [mock_result]

            # Run
            new_state = await node_retrieve_context(state)

            # Assert
            self.assertIn("Context Text", new_state["rag_context"])
            self.assertEqual(new_state["rag_sources"], ["Test Source"])
            mock_search.assert_called_once()


if __name__ == "__main__":
    unittest.main()
