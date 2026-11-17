import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DIR = Path(tempfile.mkdtemp(prefix="gamestats-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR / 'test.db'}"
os.environ["AGENT_API_KEY"] = "test-secret"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["TIMEZONE"] = "Europe/Paris"
os.environ["STEAM_API_KEY"] = ""
os.environ["STEAM_ID"] = ""
os.environ["IGDB_CLIENT_ID"] = ""
os.environ["IGDB_CLIENT_SECRET"] = ""

import pytest
from fastapi.testclient import TestClient

from database import Base, engine
from main import app

ADMIN_CREDENTIALS = {
    "username": "admin",
    "email": "admin@example.com",
    "password": "admin-password",
}


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def admin_credentials():
    return dict(ADMIN_CREDENTIALS)


@pytest.fixture
def anon_client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(admin_credentials):
    with TestClient(app) as test_client:
        response = test_client.post("/api/auth/setup", json=admin_credentials)
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture
def agent_headers():
    return {"X-Agent-Key": "test-secret"}
