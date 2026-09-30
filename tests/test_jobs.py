import os

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MAIL_DOMAIN", "test.example.com")

from api.main import app  # noqa: E402

@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_create_and_get_job(client):
    r = await client.post("/api/v1/jobs/", json={"label": "test"})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "waiting"
    assert "@" in data["email"]

    r2 = await client.get(f"/api/v1/jobs/{data['job_id']}")
    assert r2.status_code == 200
    assert r2.json()["label"] == "test"
    assert r2.json()["analysis"] is None

@pytest.mark.asyncio
async def test_get_missing_job(client):
    r = await client.get("/api/v1/jobs/nieistnieje")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_dns_invalid_type(client):
    r = await client.get("/api/v1/dns/example.com/INVALID")
    assert r.status_code == 400

@pytest.mark.network
@pytest.mark.asyncio
async def test_ssl_check(client):
    r = await client.get("/api/v1/ssl/github.com")
    assert r.status_code == 200
    assert r.json()["days_left"] > 0

@pytest.mark.network
@pytest.mark.asyncio
async def test_dns_check(client):
    r = await client.get("/api/v1/dns/github.com/A")
    assert r.status_code == 200
    assert len(r.json()["servers"]) > 0
