import pytest
from fastapi.testclient import TestClient
from main import Shipment, app, store

client = TestClient(app)

@pytest.fixture(autouse = True)
def clear() -> None:
    original = dict(store)
    store.clear()
    store["shipment-001"]= Shipment(
        id = "shipment-001",
        order_id = "order-77",
        destination = "Москва, Зеленоград",
        status = 'created'
    )
    yield
    store.clear()
    store.update(original)


def test_filter_by_status(): 
    response = client.get("/shipments", params={"status": "created"}) 
    assert response.status_code == 200 
    assert [item["id"] for item in response.json()] == ["shipment-001"] 

def test_creation_returns_location_header(): 
    response = client.post("/shipments", json = {"order_id" : "123",  "destination" : "55555"})
    assert response.status_code == 201 
    assert response.headers["location"] == f"/shipments/{response.json()['id']}"  

def test_request_id_is_returned(): 
    response = client.get("/health", headers={"X-Request-ID": "lab2-check"}) 
    assert response.headers["x-request-id"] == "lab2-check" 
    assert float(response.headers["x-process-time-ms"]) >= 0