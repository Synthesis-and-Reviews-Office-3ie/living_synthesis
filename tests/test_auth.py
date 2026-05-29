"""
Tests for authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestSignup:
    """Tests for POST /auth/signup"""
    
    def test_signup_success(self, client: TestClient):
        """Should create a new user."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "name": "New User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password
    
    def test_signup_duplicate_email(self, client: TestClient, test_user):
        """Should reject duplicate email."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",  # Same as test_user
                "password": "password123",
                "name": "Another User"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_signup_invalid_email(self, client: TestClient):
        """Should reject invalid email format."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "not-an-email",
                "password": "password123",
                "name": "Bad Email"
            }
        )
        assert response.status_code == 422  # Validation error


class TestLogin:
    """Tests for POST /auth/login"""
    
    def test_login_success(self, client: TestClient, test_user):
        """Should return access token for valid credentials."""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client: TestClient, test_user):
        """Should reject wrong password."""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Should reject login for nonexistent user."""
        response = client.post(
            "/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "password123"
            }
        )
        assert response.status_code == 401


class TestProfile:
    """Tests for /auth/me endpoint"""
    
    def test_get_profile_authenticated(self, client: TestClient, auth_headers):
        """Should return current user profile."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
    
    def test_get_profile_unauthenticated(self, client: TestClient):
        """Should reject unauthenticated request."""
        response = client.get("/auth/me")
        # FastAPI HTTPBearer returns 403 when no credentials provided
        assert response.status_code in [401, 403]
    
    def test_update_profile(self, client: TestClient, auth_headers):
        """Should update user name."""
        response = client.put(
            "/auth/me",
            json={"name": "Updated Name"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
    
    def test_update_llm_model(self, client: TestClient, auth_headers):
        """Should update user's preferred LLM model."""
        response = client.put(
            "/auth/me",
            json={"preferred_llm_model": "gpt-4o-mini"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["preferred_llm_model"] == "gpt-4o-mini"
    
    def test_get_available_models(self, client: TestClient, auth_headers):
        """Should return available models for user's tier."""
        response = client.get(
            "/auth/models",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "current_model" in data
        assert len(data["models"]) > 0


class TestPasswordReset:
    """Tests for password reset flow"""
    
    def test_request_reset_existing_user(self, client: TestClient, test_user):
        """Should accept reset request for existing user."""
        response = client.post(
            "/auth/password-reset/request",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 200
        # Should not reveal if user exists
        assert "email has been sent" in response.json()["message"].lower()
    
    def test_request_reset_nonexistent_user(self, client: TestClient):
        """Should return same message for nonexistent user (prevent enumeration)."""
        response = client.post(
            "/auth/password-reset/request",
            json={"email": "nobody@example.com"}
        )
        assert response.status_code == 200
        # Same message to prevent email enumeration
        assert "email has been sent" in response.json()["message"].lower()
