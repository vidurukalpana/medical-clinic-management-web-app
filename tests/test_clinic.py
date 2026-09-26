import json

from fastapi.testclient import TestClient

from app.services.clinic import CLINIC_CONTACT_PATH


def test_clinic_contact_is_public_and_matches_the_content_file(client: TestClient) -> None:
    response = client.get("/api/clinic-contact-details")

    assert response.status_code == 200
    assert response.json() == json.loads(CLINIC_CONTACT_PATH.read_text(encoding="utf-8"))
