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

def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_seed_shipment_is_created() -> None:
    response = client.get("/shipments/shipment-001")
    assert response.status_code == 200
    assert response.json()["status"] == "created"


def test_shipment0() -> None:
    shimp1 = client.post("/shipments", json = {"order_id" : "0",  "destination" : "55555"})

    assert shimp1.status_code == 201

def test_shipment() -> None:
    shimp1 = client.post("/shipments", json = {"order_id" : "0",  "destination" : "55555"})
    shimp2 = client.post("/shipments", json = {"order_id" : "0",  "destination" : "111111"})

    assert shimp2.status_code == 407

def test_shipment2() -> None:
    shimp1 = client.post("/shipments", json = {"order_id" : "0",  "destination" : "555"})

    assert shimp1.status_code == 422

def test_shipment3() -> None:
    shimp1 = client.post("/shipments", json = {"order_id" : "0",  "destination" : "555123"})
    
    client.post(f"/shipments/{shimp1.json()["id"]}/dispatch")
    test = client.post(f"/shipments/{shimp1.json()["id"]}/dispatch")

    assert test.status_code == 409

def test_shipment4() -> None:
    shimp1 = client.post("/shipments", json = {"order_id" : "15",  "destination" : "5555123"})
    
    test = client.post(f"/shipments/{shimp1.json()["id"]}/dispatch")

    assert test.status_code == 200

def test_shipment5() -> None:
    test = client.post("/shipments/0/dispatch")

    assert test.status_code == 404