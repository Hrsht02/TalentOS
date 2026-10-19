from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_docs_are_available_in_development():
    response = TestClient(app).get("/docs")
    assert response.status_code == 200



def test_recruitment_workflow_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/assessments/questions/aptitude" in paths
    assert "/api/v1/assessments/questions/coding" in paths
    assert "/api/v1/assessments/my-invites" in paths
    assert "/api/v1/assessments/invites/{invite_id}/coding-submissions" in paths
    assert "/api/v1/jobs/{job_id}/ranking" in paths
