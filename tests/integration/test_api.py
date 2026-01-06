"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test basic health check."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_liveness_check(self, client: TestClient) -> None:
        """Test liveness probe."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestTaskEndpoints:
    """Tests for task management endpoints."""

    @pytest.mark.skip(reason="Requires NATS connection")
    def test_create_task(self, client: TestClient) -> None:
        """Test creating a task."""
        response = client.post(
            "/api/v1/tasks",
            json={
                "name": "Test Task",
                "description": "A test task",
                "input_data": {"key": "value"},
                "priority": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Task"
        assert data["status"] == "pending"

    def test_list_tasks(self, client: TestClient) -> None:
        """Test listing tasks."""
        response = client.get("/api/v1/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestAgentEndpoints:
    """Tests for agent management endpoints."""

    def test_list_agents(self, client: TestClient) -> None:
        """Test listing agents."""
        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestWorkflowEndpoints:
    """Tests for workflow management endpoints."""

    def test_list_workflows(self, client: TestClient) -> None:
        """Test listing workflows."""
        response = client.get("/api/v1/workflows")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
