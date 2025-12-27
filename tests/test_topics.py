"""
Tests for topics endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestTopicsCRUD:
    """Tests for topics CRUD operations"""
    
    def test_list_topics_empty(self, client: TestClient, auth_headers):
        """Should return empty list when no topics exist."""
        response = client.get("/topics", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_topic(self, client: TestClient, auth_headers):
        """Should create a new topic."""
        response = client.post(
            "/topics",
            json={
                "name": "LLMs in Healthcare",
                "description": "Machine learning and LLMs applied to healthcare",
                "queries": {
                    "openalex": "large language model healthcare",
                    "pubmed": "LLM AND healthcare"
                },
                "frequency": "weekly"
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "LLMs in Healthcare"
        assert data["queries"]["pubmed"] == "LLM AND healthcare"
        assert data["frequency"] == "weekly"
    
    def test_create_topic_unauthenticated(self, client: TestClient):
        """Should reject unauthenticated topic creation."""
        response = client.post(
            "/topics",
            json={
                "name": "Test Topic",
                "queries": {"openalex": "test"}
            }
        )
        # FastAPI HTTPBearer returns 403 when no credentials provided
        assert response.status_code in [401, 403]
    
    def test_free_tier_topic_limit(self, client: TestClient, auth_headers, db):
        """Free tier users should be limited to 1 topic."""
        # Create first topic
        response = client.post(
            "/topics",
            json={"name": "Topic 1", "queries": {"openalex": "test1"}},
            headers=auth_headers
        )
        assert response.status_code == 201
        
        # Try to create second topic
        response = client.post(
            "/topics",
            json={"name": "Topic 2", "queries": {"openalex": "test2"}},
            headers=auth_headers
        )
        assert response.status_code == 403
        assert "limit" in response.json()["detail"].lower()
    
    def test_pro_tier_topic_limit(self, client: TestClient, pro_auth_headers, db):
        """Pro tier users should be allowed 3 topics."""
        for i in range(3):
            response = client.post(
                "/topics",
                json={"name": f"Topic {i+1}", "queries": {"openalex": f"test{i}"}},
                headers=pro_auth_headers
            )
            assert response.status_code == 201
        
        # Fourth topic should fail
        response = client.post(
            "/topics",
            json={"name": "Topic 4", "queries": {"openalex": "test4"}},
            headers=pro_auth_headers
        )
        assert response.status_code == 403
    
    def test_get_topic(self, client: TestClient, auth_headers):
        """Should retrieve a specific topic."""
        # Create a topic first
        create_response = client.post(
            "/topics",
            json={"name": "Get Test", "queries": {"openalex": "test"}},
            headers=auth_headers
        )
        topic_id = create_response.json()["id"]
        
        # Get it
        response = client.get(f"/topics/{topic_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"
    
    def test_get_topic_not_found(self, client: TestClient, auth_headers):
        """Should return 404 for nonexistent topic."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/topics/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
    
    def test_update_topic(self, client: TestClient, auth_headers):
        """Should update a topic."""
        # Create
        create_response = client.post(
            "/topics",
            json={"name": "Original Name", "queries": {"openalex": "test"}},
            headers=auth_headers
        )
        topic_id = create_response.json()["id"]
        
        # Update
        response = client.put(
            f"/topics/{topic_id}",
            json={"name": "Updated Name", "description": "New description"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["description"] == "New description"
    
    def test_delete_topic(self, client: TestClient, auth_headers):
        """Should delete a topic."""
        # Create
        create_response = client.post(
            "/topics",
            json={"name": "To Delete", "queries": {"openalex": "test"}},
            headers=auth_headers
        )
        topic_id = create_response.json()["id"]
        
        # Delete
        response = client.delete(f"/topics/{topic_id}", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/topics/{topic_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestTopicFrequency:
    """Tests for topic frequency restrictions"""
    
    def test_free_tier_daily_forbidden(self, client: TestClient, auth_headers):
        """Free tier should not be able to set daily frequency."""
        response = client.post(
            "/topics",
            json={
                "name": "Daily Topic",
                "queries": {"openalex": "test"},
                "frequency": "daily"
            },
            headers=auth_headers
        )
        assert response.status_code == 403
        assert "daily" in response.json()["detail"].lower()
    
    def test_pro_tier_daily_allowed(self, client: TestClient, pro_auth_headers):
        """Pro tier should be able to set daily frequency."""
        response = client.post(
            "/topics",
            json={
                "name": "Daily Topic",
                "queries": {"openalex": "test"},
                "frequency": "daily"
            },
            headers=pro_auth_headers
        )
        assert response.status_code == 201
        assert response.json()["frequency"] == "daily"
