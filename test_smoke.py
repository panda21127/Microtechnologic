from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_seed_shipment_is_created() -> None:
    response = client.get("/shipments/shipment-001")
    assert response.status_code == 200
    assert response.json()["status"] == "created"

