"""Data storage: an in-memory store for tests, and PostgreSQL for real deployments."""

import copy
import json

import psycopg
from psycopg.rows import dict_row

from app.seed import SAMPLE_STATIONS


class MemoryStore:
    kind = "memory"

    def __init__(self, seed: bool = True) -> None:
        self._stations: list[dict] = []
        self._next_id = 1
        if seed:
            for station in SAMPLE_STATIONS:
                self.create(copy.deepcopy(station))

    def init(self) -> None:
        pass

    def ping(self) -> None:
        pass

    def list(self) -> list[dict]:
        return [dict(s) for s in self._stations]

    def get(self, station_id: int) -> dict | None:
        found = next((s for s in self._stations if s["id"] == station_id), None)
        return dict(found) if found else None

    def create(self, data: dict) -> dict:
        station = {"id": self._next_id, **data}
        self._next_id += 1
        self._stations.append(station)
        return dict(station)

    def update(self, station_id: int, changes: dict) -> dict | None:
        for station in self._stations:
            if station["id"] == station_id:
                station.update(changes)
                return dict(station)
        return None


class PostgresStore:
    """Opens a short-lived connection per operation.

    Simple and robust: if the database restarts, the next request just opens a
    new connection, so the app never holds on to a broken one.
    """

    kind = "postgres"

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=3)

    def init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stations (
                  id SERIAL PRIMARY KEY,
                  name VARCHAR(120) NOT NULL,
                  area VARCHAR(80) NOT NULL,
                  lat DOUBLE PRECISION NOT NULL,
                  lng DOUBLE PRECISION NOT NULL,
                  fuels JSONB NOT NULL,
                  petrol_price INTEGER,
                  is_open BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            count = conn.execute("SELECT COUNT(*) AS n FROM stations").fetchone()["n"]
            if count == 0:
                for station in SAMPLE_STATIONS:
                    self._insert(conn, station)

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1")

    @staticmethod
    def _insert(conn, data: dict) -> dict:
        return conn.execute(
            """
            INSERT INTO stations (name, area, lat, lng, fuels, petrol_price, is_open)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
            """,
            (data["name"], data["area"], data["lat"], data["lng"],
             json.dumps(data["fuels"]), data.get("petrol_price"), data.get("is_open", True)),
        ).fetchone()

    def list(self) -> list[dict]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM stations ORDER BY id").fetchall()

    def get(self, station_id: int) -> dict | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM stations WHERE id = %s", (station_id,)).fetchone()

    def create(self, data: dict) -> dict:
        with self._connect() as conn:
            return self._insert(conn, data)

    def update(self, station_id: int, changes: dict) -> dict | None:
        if not changes:
            return self.get(station_id)
        allowed = {"petrol_price", "is_open", "fuels"}
        sets, values = [], []
        for key, value in changes.items():
            if key not in allowed:
                continue
            sets.append(f"{key} = %s")
            values.append(json.dumps(value) if key == "fuels" else value)
        values.append(station_id)
        with self._connect() as conn:
            return conn.execute(
                f"UPDATE stations SET {', '.join(sets)} WHERE id = %s RETURNING *", values
            ).fetchone()


def create_store(database_url: str):
    return PostgresStore(database_url) if database_url else MemoryStore()
