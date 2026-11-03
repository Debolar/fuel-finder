"""Fuel Finder API: find the fuel stations nearest to you."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.geo import distance_km
from app.store import create_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("fuel-finder")

FUELS = ["petrol", "diesel", "cng"]
Fuel = Literal["petrol", "diesel", "cng"]
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class StationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    area: str = Field(min_length=1, max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    fuels: list[Fuel] = Field(min_length=1)
    petrol_price: int | None = Field(default=None, gt=0)
    is_open: bool = True


class StationUpdate(BaseModel):
    fuels: list[Fuel] | None = Field(default=None, min_length=1)
    petrol_price: int | None = Field(default=None, gt=0)
    is_open: bool | None = None


def create_app(store=None) -> FastAPI:
    store = store or create_store(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Retry the database on startup: in Docker Compose or Kubernetes,
        # the database is often not ready the moment the app starts.
        for attempt in range(1, 11):
            try:
                store.init()
                break
            except Exception as err:  # noqa: BLE001
                if attempt == 10:
                    log.error("Could not connect to the database: %s", err)
                    raise
                log.info("Database not ready (attempt %s/10), retrying in 3s", attempt)
                time.sleep(3)
        log.info(
            "fuel-finder v%s started (store: %s, env: %s)",
            settings.app_version, store.kind, settings.environment,
        )
        yield

    app = FastAPI(title="Fuel Finder", version=settings.app_version, lifespan=lifespan)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        log.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, ms)
        return response

    # ---- Health checks (Docker, Kubernetes, load balancers, smoke tests) ----

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        try:
            store.ping()
            return {"status": "ready", "store": store.kind}
        except Exception as err:  # noqa: BLE001
            return JSONResponse(status_code=503, content={"status": "not ready", "error": str(err)})

    # ---- API ----

    @app.get("/api/info")
    def info():
        return {
            "app": "fuel-finder",
            "version": settings.app_version,
            "environment": settings.environment,
            "store": store.kind,
            "fuels": FUELS,
        }

    @app.get("/api/stations")
    def list_stations(
        lat: float | None = Query(default=None, ge=-90, le=90),
        lng: float | None = Query(default=None, ge=-180, le=180),
        fuel: Fuel | None = None,
        open_only: bool = False,
        limit: int = Query(default=20, ge=1, le=100),
    ):
        if (lat is None) != (lng is None):
            raise HTTPException(status_code=400, detail="give both lat and lng, or neither")

        stations = store.list()
        if fuel:
            stations = [s for s in stations if fuel in s["fuels"]]
        if open_only:
            stations = [s for s in stations if s["is_open"]]

        if lat is not None:
            for s in stations:
                s["distance_km"] = round(distance_km(lat, lng, s["lat"], s["lng"]), 2)
            stations.sort(key=lambda s: s["distance_km"])

        return stations[:limit]

    @app.get("/api/stations/{station_id}")
    def get_station(station_id: int):
        station = store.get(station_id)
        if not station:
            raise HTTPException(status_code=404, detail="station not found")
        return station

    @app.post("/api/stations", status_code=201)
    def add_station(body: StationIn):
        return store.create(body.model_dump())

    @app.patch("/api/stations/{station_id}")
    def update_station(station_id: int, body: StationUpdate):
        station = store.update(station_id, body.model_dump(exclude_unset=True))
        if not station:
            raise HTTPException(status_code=404, detail="station not found")
        return station

    # The website itself, served from the same container.
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


app = create_app()
