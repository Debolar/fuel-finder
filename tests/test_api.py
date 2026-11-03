"""Automated tests for the Fuel Finder API. Run with: pytest"""

import pytest
from fastapi.testclient import TestClient

from app.geo import distance_km
from app.main import create_app
from app.store import MemoryStore

# Coordinates of Yaba, Lagos, used as "my location" in several tests.
YABA = {"lat": 6.5095, "lng": 3.3711}


@pytest.fixture
def client():
    # A fresh in-memory store with the sample stations for every test.
    with TestClient(create_app(store=MemoryStore())) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ready_reports_store(client):
    assert client.get("/ready").json()["store"] == "memory"


def test_ready_returns_503_when_store_is_down():
    store = MemoryStore()

    def broken_ping():
        raise RuntimeError("database unreachable")

    store.ping = broken_ping
    with TestClient(create_app(store=store)) as c:
        assert c.get("/ready").status_code == 503


def test_info_lists_fuels(client):
    body = client.get("/api/info").json()
    assert body["app"] == "fuel-finder"
    assert "diesel" in body["fuels"]


def test_lists_sample_stations(client):
    assert len(client.get("/api/stations").json()) == 12


def test_nearest_station_comes_first(client):
    stations = client.get("/api/stations", params=YABA).json()
    assert stations[0]["area"] == "Yaba"
    assert stations[0]["distance_km"] == 0
    distances = [s["distance_km"] for s in stations]
    assert distances == sorted(distances)


def test_filter_by_fuel(client):
    stations = client.get("/api/stations", params={"fuel": "cng"}).json()
    assert stations and all("cng" in s["fuels"] for s in stations)


def test_open_only_hides_closed_stations(client):
    stations = client.get("/api/stations", params={"open_only": "true"}).json()
    assert all(s["is_open"] for s in stations)
    assert len(stations) == 10


def test_limit(client):
    assert len(client.get("/api/stations", params={**YABA, "limit": 3}).json()) == 3


def test_rejects_lat_without_lng(client):
    assert client.get("/api/stations", params={"lat": 6.5}).status_code == 400


def test_rejects_unknown_fuel(client):
    assert client.get("/api/stations", params={"fuel": "kerosene"}).status_code == 422


def test_add_station(client):
    res = client.post("/api/stations", json={
        "name": "Test Station", "area": "Oshodi", "lat": 6.55, "lng": 3.34,
        "fuels": ["petrol"], "petrol_price": 1000,
    })
    assert res.status_code == 201
    assert res.json()["id"] == 13


def test_rejects_station_without_fuels(client):
    res = client.post("/api/stations", json={
        "name": "X", "area": "Y", "lat": 6.5, "lng": 3.3, "fuels": [],
    })
    assert res.status_code == 422


def test_update_price_and_open_status(client):
    res = client.patch("/api/stations/1", json={"petrol_price": 999, "is_open": False})
    assert res.status_code == 200
    assert res.json()["petrol_price"] == 999
    assert res.json()["is_open"] is False


def test_missing_station_returns_404(client):
    assert client.get("/api/stations/999").status_code == 404


def test_distance_formula():
    # Ikeja to Victoria Island is roughly 20 km in a straight line.
    assert 18 < distance_km(6.6018, 3.3515, 6.4281, 3.4219) < 22
