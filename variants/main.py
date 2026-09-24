import os
from typing import Literal
from uuid import uuid4

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "shipment-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


class ShipmentCreate(BaseModel):
    order_id: str = Field(min_length=1)
    destination: str = Field(min_length=5, max_length=240)

class Shipment(ShipmentCreate):
    id: str
    status: Literal["created", "in_transit", "delivered"] = "created"



store: dict[str, Shipment] = {
    "shipment-001": Shipment(id="shipment-001", order_id="order-77", destination="Москва, Зеленоград")
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/shipments", response_model=list[Shipment])
def list_shipments() -> list[Shipment]:
    return list(store.values())

@app.get("/shipments/{shipment_id}", response_model=Shipment)
def get_shipment(shipment_id: str) -> Shipment:
    if shipment_id not in store:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return store[shipment_id]


@app.post("/shipments", response_model=Shipment, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate) -> Shipment:
    
    if (store != None):
        for shape in store.values():
            if shape.order_id == payload.order_id:
                raise HTTPException(status_code=418, detail="Order_id is already created")
    
    shipmentCreate = Shipment(
        id = str(uuid4()),
        order_id = payload.order_id,
        destination = payload.destination,
        status = 'created'
    )

    store[shipmentCreate.id]=shipmentCreate
    return shipmentCreate


@app.post("/shipments/{shipment_id}/dispatch", response_model=Shipment)
def dispatch_shipment(shipment_id: str) -> Shipment:
    shipmentCreate = store.get(shipment_id)
    if shipmentCreate is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if shipmentCreate.status != "created":
        raise HTTPException(status_code=409, detail="Product is already created")

    shimpered = shipmentCreate.model_copy(update = {'status' : 'in_transit'})
    store[shipment_id] = shimpered
    return shimpered