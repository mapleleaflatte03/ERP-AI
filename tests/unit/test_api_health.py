import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.api.main import app, check_database_connection

client = TestClient(app)

@pytest.mark.asyncio
@patch("src.api.main.check_database_connection", new_callable=AsyncMock)
async def test_health_check_db_success(mock_db):
    mock_db.return_value = (True, None)

    with patch("src.api.main.check_storage_sync", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert "services" in data
        assert "database" in data["services"]
        assert data["services"]["database"]["status"] == "healthy"

@pytest.mark.asyncio
@patch("src.api.main.check_database_connection", new_callable=AsyncMock)
async def test_health_check_db_failure(mock_db):
    mock_db.return_value = (False, "Connection failed")

    with patch("src.api.main.check_storage_sync", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert "services" in data
        assert "database" in data["services"]
        assert data["services"]["database"]["status"] == "unhealthy"
        assert data["services"]["database"]["error"] == "Connection failed"

@pytest.mark.asyncio
@patch("src.db.get_connection")
async def test_check_database_connection_impl_success(mock_get_conn):
    # Mock context manager
    mock_conn = AsyncMock()
    # get_connection returns an async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_get_conn.return_value = mock_ctx

    success, error = await check_database_connection()
    assert success is True
    assert error is None
    mock_conn.execute.assert_called_with("SELECT 1")

@pytest.mark.asyncio
@patch("src.db.get_connection")
async def test_check_database_connection_impl_failure(mock_get_conn):
    # Mocking failure to acquire connection or execute
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.side_effect = Exception("DB Down")
    mock_get_conn.return_value = mock_ctx

    success, error = await check_database_connection()
    assert success is False
    assert error == "DB Down"
