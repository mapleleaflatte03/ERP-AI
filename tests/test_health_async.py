import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from api.main import app

class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.main.get_pool", new_callable=AsyncMock)
    @patch("api.main.get_qdrant_client")
    @patch("api.main.get_minio_client")
    def test_health_check_healthy(self, mock_minio, mock_qdrant, mock_pool):
        # Setup DB Mock
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "1"

        mock_pool_obj = MagicMock()
        mock_acquire_ctx = AsyncMock()
        mock_acquire_ctx.__aenter__.return_value = mock_conn
        mock_acquire_ctx.__aexit__.return_value = None
        mock_pool_obj.acquire.return_value = mock_acquire_ctx
        mock_pool.return_value = mock_pool_obj

        # Mock Qdrant
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.health_check = AsyncMock(return_value=True)
        mock_qdrant.return_value = mock_qdrant_client

        # Mock MinIO (sync)
        mock_minio_client = MagicMock()
        mock_minio_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_minio_client

        response = self.client.get("/health")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "ok")

    @patch("api.main.get_pool", new_callable=AsyncMock)
    @patch("api.main.get_qdrant_client")
    @patch("api.main.get_minio_client")
    def test_health_check_degraded(self, mock_minio, mock_qdrant, mock_pool):
        # Mock DB Failure
        mock_pool.side_effect = Exception("DB Down")

        # Mock Qdrant Healthy
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.health_check = AsyncMock(return_value=True)
        mock_qdrant.return_value = mock_qdrant_client

        # Mock MinIO Healthy
        mock_minio_client = MagicMock()
        mock_minio_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_minio_client

        response = self.client.get("/health")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "degraded")
        self.assertEqual(data["components"]["database"]["status"], "unhealthy")
        self.assertEqual(data["components"]["vector_db"]["status"], "healthy")

if __name__ == "__main__":
    unittest.main()
