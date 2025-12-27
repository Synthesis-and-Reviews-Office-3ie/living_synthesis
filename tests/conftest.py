"""
Pytest configuration and fixtures for API tests.
"""

import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Set test environment BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET"] = "test-secret-key"

from app.database import Base
from app.models import User, UserTier
from app.auth import hash_password, create_access_token

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create tables once
Base.metadata.create_all(bind=engine)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Shared connection for all tests to ensure same database state
_connection = None
_session = None


def get_test_db():
    """Override database dependency for tests."""
    global _session
    try:
        yield _session
    finally:
        pass  # Don't close - managed by fixture


@pytest.fixture(scope="function")
def db():
    """Get a database session for tests with transaction rollback."""
    global _connection, _session
    
    # Start a connection and transaction
    _connection = engine.connect()
    transaction = _connection.begin()
    
    # Create session bound to this connection
    _session = Session(bind=_connection)
    
    yield _session
    
    # Rollback everything after test
    _session.close()
    transaction.rollback()
    _connection.close()
    _session = None
    _connection = None


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with the same database session."""
    from app.main import app
    from app.database import get_db
    
    # Override the database dependency to use our test session
    app.dependency_overrides[get_db] = get_test_db
    
    # Enable raise_server_exceptions to see actual errors
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Test User",
        tier=UserTier.FREE,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def pro_user(db) -> User:
    """Create a pro tier user."""
    user = User(
        email="pro@example.com",
        hashed_password=hash_password("propassword123"),
        name="Pro User",
        tier=UserTier.PRO,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Get authentication headers for test user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pro_auth_headers(pro_user) -> dict:
    """Get authentication headers for pro user."""
    token = create_access_token(data={"sub": str(pro_user.id)})
    return {"Authorization": f"Bearer {token}"}
