from fastapi.testclient import TestClient


def test_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
