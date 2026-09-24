import os
from typing import Literal
from uuid import uuid4
from enum import StrEnum

from time import perf_counter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "shipment-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

# server einee
# Ввести на 8000 порту, другой на 8001
# server proxy_pass http::localhost
# Написать заголовок который вытягивает переменную окружения и добавляется в заголовок x-upstream
# Определить через unicorn
# Настроить балансировку



app.add_middleware(
    CORSMiddleware,
    allow_methods=[""],
    allow_headers=[""],
)

class ShipmentStatus(StrEnum):
    CREATED = "created"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"

class ShipmentPatch(BaseModel):
    status: ShipmentStatus

class ShipmentCreate(BaseModel):
    order_id: str = Field(min_length=1)
    destination: str = Field(min_length=5, max_length=240)

class Shipment(ShipmentCreate):
    id: str
    status: Literal["created", "in_transit", "delivered"] = "created"



store: dict[str, Shipment] = {
    "shipment-001": Shipment(id="shipment-001", order_id="order-77", destination="Москва, Зеленоград")
}

@app.middleware("http")
async def add_diagnostic_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = (
    f"{(perf_counter() - started) * 1000:.2f}"
    )
    return response

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}

@app.get("/shipments", response_model=list[Shipment])
def list_shipments(
    status: Annotated[ShipmentStatus | None, Query()] = None,
    order_id: Annotated[str | None, Query()] = None,
) -> list[Shipment]:
    shipments = list(store.values())
    if status is not None:
        return [s for s in shipments if s.status == status]

    if order_id is not None:
        return [s for s in shipments if s.order_id == order_id]

    return shipments

@app.get("/shipments/{shipment_id}", response_model=Shipment)
def get_shipment(shipment_id: str) -> Shipment:
    if shipment_id not in store:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return store[shipment_id]


@app.post("/shipments", response_model=Shipment, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate, response: Response) -> Shipment:
    
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
    response.headers["Location"] = f"/shipments/{shipmentCreate.id}"
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


@app.patch("/shipments/{shipment_id}", response_model=Shipment)
def patch_shipment(shipment_id: str, payload: ShipmentPatch) -> Shipment:
    shipment = store.get(shipment_id)
    if shipment is None:
        raise HTTPException(404, "Shipment not found")
    if shipment.status != "created":
        raise HTTPException(409, "Published shipment cannot be edited")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "At least one field is required")
    updated = shipment.model_copy(update=changes)
    store[shipment_id] = updated
    return updated
