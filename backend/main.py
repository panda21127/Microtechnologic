import os
from contextlib import asynccontextmanager
from datetime import datetime
from enum import StrEnum
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


SERVICE_NAME = os.getenv("SERVICE_NAME", "shipment-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "change_me")

DATABASE_URL = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class ShipmentORM(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    destination: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    tracking_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
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
    tracking_code: str | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_dto(row: ShipmentORM) -> Shipment:
    return Shipment(
        id=row.id,
        order_id=row.order_id,
        destination=row.destination,
        status=row.status,
        tracking_code=row.tracking_code,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION, lifespan=lifespan)


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


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Database is not ready: {exc}"
        ) from exc


@app.get("/shipments", response_model=list[Shipment])
def list_shipments(
    db: Session = Depends(get_db),
    status: Annotated[ShipmentStatus | None, Query()] = None,
    order_id: Annotated[str | None, Query()] = None,
    tracking_code: Annotated[str | None, Query()] = None,
) -> list[Shipment]:
    stmt = select(ShipmentORM)
    if status is not None:
        stmt = stmt.where(ShipmentORM.status == status.value)
    if order_id is not None:
        stmt = stmt.where(ShipmentORM.order_id == order_id)
    if tracking_code is not None:
        stmt = stmt.where(ShipmentORM.tracking_code == tracking_code)
    rows = db.execute(stmt).scalars().all()
    return [to_dto(row) for row in rows]


@app.get("/shipments/{shipment_id}", response_model=Shipment)
def get_shipment(shipment_id: str, db: Session = Depends(get_db)) -> Shipment:
    row = db.get(ShipmentORM, shipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return to_dto(row)


@app.post("/shipments", response_model=Shipment, status_code=status.HTTP_201_CREATED)
def create_shipment(
    payload: ShipmentCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> Shipment:
    existing = db.execute(
        select(ShipmentORM).where(ShipmentORM.order_id == payload.order_id)
    ).scalar_one_or_none()
    if existing is not None:
        # В ЛР2 для дубликата использовался 418; сохраняем контракт.
        raise HTTPException(status_code=418, detail="Order_id is already created")

    row = ShipmentORM(
        id=str(uuid4()),
        order_id=payload.order_id,
        destination=payload.destination,
        status="created",
        tracking_code=None,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error") from exc
    db.refresh(row)
    response.headers["Location"] = f"/shipments/{row.id}"
    return to_dto(row)


@app.post("/shipments/{shipment_id}/dispatch", response_model=Shipment)
def dispatch_shipment(shipment_id: str, db: Session = Depends(get_db)) -> Shipment:
    row = db.get(ShipmentORM, shipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if row.status != "created":
        raise HTTPException(status_code=409, detail="Shipment is already dispatched")

    row.status = "in_transit"
    db.commit()
    db.refresh(row)
    return to_dto(row)


@app.patch("/shipments/{shipment_id}", response_model=Shipment)
def patch_shipment(
    shipment_id: str,
    payload: ShipmentPatch,
    db: Session = Depends(get_db),
) -> Shipment:
    row = db.get(ShipmentORM, shipment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if row.status != "created":
        raise HTTPException(status_code=409, detail="Shipment cannot be edited")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one field is required")

    if "status" in changes:
        row.status = str(changes["status"])

    db.commit()
    db.refresh(row)
    return to_dto(row)