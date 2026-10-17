# Setup and deployment

The application runs against real local MongoDB or Atlas. No external deployment has been performed. The checked-in Dockerfile, Compose file and Render blueprint describe deployment; Docker is unavailable on the development workstation, so image build/start verification remains an operator step.

## Local setup

Use Python 3.13 for the tested scientific-runtime lock and Node 22+ for Vite tooling. Start MongoDB 8, then follow the README's virtual-environment installation and `backend/.env` setup. Neither Node nor a generative-AI key is needed by the API. Browser checks use installed Google Chrome and the project's Playwright dependency.

```powershell
# Repository root, after copying backend/.env.example to backend/.env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

Open `http://127.0.0.1:4173` for the production PWA. `npm run dev` uses port 5173 and intentionally does not register the service worker. Both local servers proxy `/api` to `http://127.0.0.1:8000`. API health is `/api/health`; the generated API contract is `/docs` and `/openapi.json` on the backend. A first import of the scientific libraries can delay readiness; wait for the health check.

## Environment variables

Backend variables belong in `backend/.env` or the hosting provider's secret environment. Never place secrets in `VITE_*` variables, which are compiled into public JavaScript.

| Variable | Meaning / example |
| --- | --- |
| `MONGODB_URI` | Local `mongodb://127.0.0.1:27017`, or the private Atlas connection string |
| `MONGODB_DATABASE` | Database name, default `pashuraksha` |
| `JWT_SECRET` | Private random secret of at least 32 characters; replacing it invalidates existing JWTs |
| `JWT_EXPIRE_MINUTES` | Session lifetime, default 480 minutes |
| `CORS_ORIGINS` | Comma-separated frontend origins including scheme and port; no wildcard in production |
| `ENVIRONMENT` | `development` locally, `production` on the live service |
| `DEMO_MODE` | `true` seeds synthetic accounts/data; must be `false` with production environment |
| `OUTBREAK_RADIUS_KM` | Default 5; validated range (0, 50] |
| `OUTBREAK_WINDOW_HOURS` | Default 72; must fit two 24-hour growth intervals |
| `OUTBREAK_ABNORMAL_THRESHOLD` | Default 40; lower than suspected threshold |
| `OUTBREAK_SUSPECTED_THRESHOLD` | Default 65; no greater than critical threshold 80 |
| `GEMINI_API_KEY` | Optional backend-only secret for PashuMitra help intent classification; empty by default |
| `GEMINI_MODEL` | Optional model ID supporting structured JSON; both Gemini settings are required to enable the adapter |
| `VITE_API_BASE_URL` | Frontend build setting: deployed API URL **including `/api`**, e.g. `https://your-api.example/api`; leave unset for local proxy |
| `VITE_PROXY_TARGET` | Local Vite process setting for backend origin, default `http://127.0.0.1:8000` |

Settings read the root `.env`, then `backend/.env`; process environment overrides both. The model artifact and metadata are versioned together in `backend/app/triage/artifacts`. Do not load untrusted joblib files. There is no required LLM, weather, Cloudinary or government API configuration.

## MongoDB Atlas

Create a database user limited to the application database and configure Atlas network access for the backend's outbound IP addresses. Supply the resulting URI privately as `MONGODB_URI`; percent-encode special characters in credentials when constructing a URI. Keep TLS enabled. The application creates its unique, TTL and `2dsphere` indexes at startup. Existing duplicate data will cause startup to fail rather than silently disable constraints.

Attachments live in the same database's `fs.files` and `fs.chunks` collections, with authorized metadata in `media`. Back up these collections together with the application records. No persistent Render filesystem is required for attachments. This uses [PyMongo's GridFS storage](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/gridfs/).

## Docker

From the repository root, after configuring `backend/.env`:

```powershell
docker compose up --build -d
docker compose logs api
```

Compose starts a private-network MongoDB with a persistent named volume and publishes only the API on local port 8000. The frontend still runs with Vite preview or a static host. Do not run this alongside another API already using port 8000. To use Atlas instead of Compose's local MongoDB:

```powershell
docker build -f backend/Dockerfile -t pashuraksha-api .
docker run --rm --env-file backend/.env -p 127.0.0.1:8000:8000 pashuraksha-api
```

The image runs as a non-root user, includes the scientific runtime and local model, and starts **one** Uvicorn worker. Process locks coordinate cluster and workflow projections. Do not increase workers or replicas until this is replaced with distributed coordination. The image excludes `.env` files and local runtime data.

## Render API and Vercel frontend

1. Use `render.yaml` as the blueprint, or create a Docker service with repository-root context and `backend/Dockerfile`. Provide `MONGODB_URI` and the final frontend's `CORS_ORIGINS`. The blueprint creates a JWT secret, disables demo mode and uses port 8000 and `/api/health`. Render supports [repository Dockerfile builds](https://render.com/docs/docker).
2. In Vercel, select root directory `frontend`, Vite framework, build command `npm run build` and output `dist`. Include source files outside the root directory so the shared `backend/app/assistant/catalog.json` is available to the frontend build. Set `VITE_API_BASE_URL` to the Render service's HTTPS URL ending in `/api`, then rebuild. The repository includes SPA rewrites and a non-cached `sw.js` header; see [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).
3. Add the exact Vercel/custom-domain origin to the API's CORS configuration. Preview deployment origins need explicit entries. Check login, an animal record, report upload and deep-link refresh over HTTPS. Inspect service-worker registration on the deployed frontend.
4. Provision professional accounts through the command below. Public registration creates farmers only. The organization must verify professional identities before provisioning.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe backend/scripts/provision_user.py --email vet@example.org --name 'District Veterinarian' --district Pune --role vet
```

The command prompts privately for a password and refuses to overwrite existing accounts. Supported roles are `farmer`, `paravet`, `vet`, `lab`, `admin`. Inside the image `PYTHONPATH` is already configured.

## Demonstration and operating limits

For a fresh rehearsal, point a development API with `DEMO_MODE=true` at a **new database name** such as `pashuraksha_rehearsal_02`; this preserves earlier records and restarts the labelled seed/replay. Demo endpoints are disabled in production. Do not enable the public demo credentials in a deployment that holds real records.

This is a single-worker hackathon prototype. Recalculation admits at most 5,000 observations in the baseline/active window and 2,000 eligible active animals per district. Offline synchronization requires an open app and usable connection; clearing browser data removes unsynced reports. File checks enforce supported signatures and an 8 MB limit, without a malware scanner. Clinical validation, backups/restore exercises, production traffic testing and external hosting verification remain deployment/field-work responsibilities.
