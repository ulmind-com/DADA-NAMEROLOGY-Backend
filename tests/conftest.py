import os
import tempfile

import pytest

# Point the app at a throwaway SQLite file before anything imports settings.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["OTP_DEV_ECHO"] = "true"
os.environ["SMTP_HOST"] = ""
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

B = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    os.close(_db_fd)
    os.unlink(_db_path)


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
