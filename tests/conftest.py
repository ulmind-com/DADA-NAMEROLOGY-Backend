"""Test setup.

Tests run against a real MongoDB using a dedicated `*_test` database that is dropped
before and after the session, so they exercise the same driver and aggregation
pipelines as production. Point TEST_MONGODB_URI at a local mongod to run offline.
"""

import os
from pathlib import Path

import pytest


def _env_from_dotenv(key: str) -> str | None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


URI = (
    os.environ.get("TEST_MONGODB_URI")
    or os.environ.get("MONGODB_URI")
    or _env_from_dotenv("MONGODB_URI")
    or "mongodb://localhost:27017"
)

# Configure the app before anything imports settings.
os.environ["MONGODB_URI"] = URI
os.environ["MONGODB_DB"] = "dada_numerology_test"
os.environ["OTP_DEV_ECHO"] = "true"
os.environ["SMTP_HOST"] = ""
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["CLOUDINARY_CLOUD_NAME"] = ""      # uploads stay disabled in tests
os.environ["CLOUDINARY_CLOUD_API_KEY"] = ""
os.environ["CLOUDINARY_CLOUD_SECRET"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.db.mongo import get_client  # noqa: E402
from app.main import app  # noqa: E402

B = "/api/v1"


@pytest.fixture(scope="session")
def client():
    get_client().drop_database("dada_numerology_test")
    with TestClient(app) as c:
        yield c
    get_client().drop_database("dada_numerology_test")


@pytest.fixture(scope="session")
def user_headers(client):
    email = "tester@example.com"
    otp = client.post(f"{B}/auth/signup/start", json={"email": email}).json()["dev_otp"]
    token = client.post(f"{B}/auth/signup/verify", json={"email": email, "code": otp}).json()[
        "signup_token"
    ]
    session = client.post(
        f"{B}/auth/signup/complete",
        json={
            "signup_token": token,
            "full_name": "Test User",
            "phone": "9531199355",
            "password": "Testing12345",
            "dob": "1995-08-15",
        },
    ).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    session = client.post(
        f"{B}/auth/login",
        json={"email": "admin@dadanumerology.com", "password": "Admin@12345"},
    ).json()
    return {"Authorization": f"Bearer {session['access_token']}"}
