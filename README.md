# Fuel Finder

A small web app that shows the fuel stations nearest to you, with fuel types, petrol prices, opening status and a link for directions. It is the second application in a DevOps practice setup, next to Journey Log.

The app code is done. Your job is the DevOps work: containerize it, give it a pipeline, and deploy it on Kubernetes alongside Journey Log.

```
Browser ──▶ Fuel Finder (Python, FastAPI) ──▶ PostgreSQL
            serves the website AND the API
```

Note the difference from Journey Log: there, Nginx served the website and a separate Node.js container served the API. Here, **one Python container serves both**. Real companies run apps built both ways, and DevOps has to handle each.

**Demo data:** the 12 stations are fictional, placed at approximate locations around Lagos, with made-up prices.

## Project structure

```
fuel-finder/
├── app/
│   ├── main.py          Routes, validation, health checks, startup retries
│   ├── config.py        Settings from environment variables
│   ├── store.py         Data layer: in-memory (tests) or PostgreSQL (real)
│   ├── geo.py           Distance calculation (haversine formula)
│   └── seed.py          The sample stations loaded on first start
├── static/              The website (HTML, CSS, JavaScript)
├── tests/test_api.py    16 automated tests (pytest)
├── requirements.txt     Packages the app needs to run
├── requirements-dev.txt Packages for testing and linting (adds pytest, ruff)
├── pyproject.toml       Settings for ruff (linter) and pytest
└── .env.example         Example environment variables
```

## Run it locally (no Docker yet)

You need **Python 3.12 or newer**.

```bash
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
# source .venv/bin/activate        # Linux / Mac
pip install -r requirements-dev.txt

pytest                              # 16 tests should pass
ruff check .                        # should print "All checks passed!"

uvicorn app.main:app --port 8000    # in-memory data
```

Open http://localhost:8000. Interactive API docs are at http://localhost:8000/docs (FastAPI makes them automatically).

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | *(empty)* | PostgreSQL connection, e.g. `postgresql://fuel:pass@db:5432/fuel`. Empty = in-memory |
| `APP_VERSION` | `dev` | Shown in the footer. Set it from your pipeline |
| `APP_ENV` | `local` | Environment name shown in the footer |

The app creates its table and loads the sample stations on first start, so no SQL setup script is needed.

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness: is the process running? |
| GET | `/ready` | Readiness: can it reach the database? `200` or `503` |
| GET | `/api/info` | Version, environment, store, fuel types |
| GET | `/api/stations` | List stations. Optional: `lat` + `lng` (sort by distance), `fuel` (`petrol`, `diesel`, `cng`), `open_only=true`, `limit` |
| GET | `/api/stations/{id}` | One station |
| POST | `/api/stations` | Add a station |
| PATCH | `/api/stations/{id}` | Update `petrol_price`, `is_open` or `fuels` |

Example: `curl "http://localhost:8000/api/stations?lat=6.5095&lng=3.3711&limit=3"`

---

# Your DevOps tasks

This time, write the files yourself first, then ask for a review. Reuse what you built for Journey Log, and note what is different.

### 1. Repository
- [ ] New GitHub repo `fuel-finder`, branch `main`, protected with a ruleset
- [ ] Add a `.gitattributes` with `* text=auto eol=lf`

### 2. Docker
- [ ] `Dockerfile` using a small Python image (for example `python:3.13-slim`)
- [ ] Copy `requirements.txt` first and install it before copying the code (same caching idea as `package.json`)
- [ ] Install only `requirements.txt`, not the dev requirements
- [ ] **Create a non-root user yourself**: unlike the Node image, Python images do not come with one
- [ ] Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`
  (`--host 0.0.0.0` lets traffic in from outside the container; `--no-access-log` avoids logging every request twice, since the app logs requests itself)
- [ ] `.dockerignore` (keep out `.venv`, `tests`, `__pycache__`, `.env`)
- [ ] `docker-compose.yml` with the app and `postgres:16-alpine`, a named volume, and a health check

### 3. CI with GitHub Actions
- [ ] On pull requests: set up Python, install `requirements-dev.txt`, run `ruff check .` and `pytest`
- [ ] Make the check required
- [ ] On merge to `main`: build, scan with Trivy, push to GitHub Container Registry, tagged with the commit ID

### 4. Kubernetes, next to Journey Log
- [ ] Its own **namespace**, `fuel-finder`
- [ ] PostgreSQL StatefulSet with storage, password in a Secret
- [ ] App Deployment (2 replicas) with liveness and readiness probes
- [ ] Reach both apps through one **Ingress**: `journey.localhost` and `fuel.localhost`

### 5. Deploy both apps at once
- [ ] **Argo CD** watching both repos, deploying each app when its `main` changes

## Built-in features to notice

- Settings from environment variables, health and readiness endpoints, startup retries, logs to stdout
- **Short-lived database connections**: each request opens its own connection, so a database restart cannot crash the app (a different solution from the fix you made in Journey Log)
- Input validation by Pydantic: invalid input returns `422`, a status code Journey Log did not use
