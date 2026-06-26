"""Integration test for the health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """Test that /health returns HTTP 200 with expected structure."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fraud-api"
    assert data["version"] == "0.1.0"
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
