import os
import tempfile

# Configurar antes de importar la app
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OTEL_ENABLED"] = "false"
os.environ["ADMIN_EMAIL"] = "admin@test.com"
os.environ["ADMIN_PASSWORD"] = "Admin123!"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123!"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def user_headers(client, admin_headers):
    client.post("/api/users", headers=admin_headers, json={
        "name": "Cliente", "email": "cliente@test.com", "password": "Cliente123", "role": "user"})
    r = client.post("/api/auth/login", json={"email": "cliente@test.com", "password": "Cliente123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
