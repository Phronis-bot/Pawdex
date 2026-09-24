from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_db_and_extensions():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["postgis"]
    assert body["pgvector"]
