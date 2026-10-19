from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_docs_are_available_in_development():
    response = TestClient(app).get("/docs")
    assert response.status_code == 200
