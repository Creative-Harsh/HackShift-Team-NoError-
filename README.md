# PashuRaksha

PashuRaksha is the PS 26128 Smart India Hackathon prototype for structured livestock health reporting, explainable triage and local disease surveillance. The working path is Farmer/Paravet report → rule and synthetic-model assessment → deterministic risk factors → MongoDB geospatial cluster detection → veterinarian review → laboratory evidence → authority confirmation. The core path has no generative-AI dependency.

All identity numbers, people, reports and replay observations are synthetic. The footer and identity screen say **“Bharat Pashudhan-compatible identity simulation”**. There is no Bharat Pashudhan, government, external laboratory, WhatsApp, weather or live-veterinarian integration.

## Stack and layout

React + Vite + TypeScript, React Router, React Hook Form/Zod, Axios, Leaflet/OSM, Recharts and Lucide form the frontend. FastAPI + Pydantic + PyMongo, scikit-learn and a versioned local artifact form the backend. MongoDB stores GeoJSON Points and uses `2dsphere` indexes. Private attachments use MongoDB GridFS in the same database, including on Atlas; they do not depend on a server filesystem or Cloudinary account. Node is frontend build/test tooling only.

```text
frontend/src/{pages,components,features/{assessment,offline,surveillance,workflow},services,hooks,layouts,types}
backend/app/{auth,database,schemas,routes,services,triage,risk_engine,geospatial,outbreak,notifications}
ml/                         # synthetic generator, training and evaluation
tests/                      # unit, API, real-Mongo and browser scenarios
docs/{ARCHITECTURE,DEMO,ML_AND_RISK_ENGINE,OUTBREAK_ENGINE,EVALUATION}.md
```

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for contracts and phase decisions and [TASKS.md](TASKS.md) for the verification log.

## Local setup

Requirements: Python 3.11+ (tested with 3.13), Node 22+, and MongoDB 8 or MongoDB Atlas.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
Copy-Item backend\.env.example backend\.env
# Set a private JWT_SECRET in backend/.env before deployment.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`. The Vite development proxy points `/api` to port 8000. Set `VITE_API_BASE_URL` for a deployed API. MongoDB must be running; a connection failure is surfaced as unavailable and never replaced with a mock database.

`DEMO_MODE=true` seeds the labelled demo accounts and 18 animals. Disable it in production. Production also requires a private JWT secret of at least 32 characters, explicit CORS origins and `DEMO_MODE=false`.

## Demo accounts and flow

Every account below uses `Demo@26128`:

| Role | Email |
| --- | --- |
| Farmer | `farmer@demo.pashuraksha.in` |
| Paravet | `paravet@demo.pashuraksha.in` |
| Veterinarian | `vet@demo.pashuraksha.in` |
| Laboratory operator | `lab@demo.pashuraksha.in` |
| District admin | `admin@demo.pashuraksha.in` |
| Second farmer | `farmer2@demo.pashuraksha.in` |

Start as Farmer, look up simulated ID `261280000001` (Gauri), and submit a structured report. The response shows “Possible …”, an assessment notice, safe actions and an exact risk-factor sum. It is not a diagnosis.

For the surveillance demonstration, sign in as District admin and open **Outbreak map**. **Replay next report** advances one persisted synthetic observation at a time. The first report is isolated; concentrated similar observations become an abnormal cluster and then a suspected outbreak. The map shows individual GeoJSON reports, risk-weighted density, filters and hotspot factors. Replay never sets official confirmation.

For the care workflow, open a report as Veterinarian, claim/assign it, record findings and recommendations, and request a target laboratory category. As Laboratory operator, move the sample through received → testing → positive/negative/inconclusive. A positive result confirms the case category only. The assigned veterinarian records control/treatment notes and closes the episode. As District admin, an active cluster can be confirmed only with matching positive laboratory evidence and an investigation note.

## PashuMitra voice companion

Click the calf at the bottom right after login. Choose English, Hindi or Hinglish, then type or explicitly enable browser speech processing and press **Talk**. Enable the speaker for spoken replies. Page guidance has separate consent. PashuMitra reads back observations for verification and points to real controls; you complete all form choices and submissions. It uses the existing rules for preliminary concern and preserves unknown information.

Text help works without a Gemini key. Optional `GEMINI_API_KEY` and `GEMINI_MODEL` enable a constrained backend help-intent adapter. Voice availability depends on the browser/device. The app does not persist assistant audio/transcripts. See [usage, permissions, limitations and tests](docs/PASHUMITRA.md). Ten Playwright assistant scenarios passed; microphone events were simulated for lifecycle verification, not measured for acoustic accuracy.

## Engineering boundaries

The triage engine combines deterministic symptom rules with a scikit-learn Random Forest trained on a documented synthetic generator. It reports held-out prototype metrics, not clinical accuracy. The risk engine budgets symptom match, model support, mortality, vaccination context, vulnerability, contact, nearby activity and cluster strength; every integer contribution is returned.

The outbreak engine deduplicates the latest observation per animal, rejects future/unknown/rejected signals, uses distance, incident time, disease and symptom agreement, recent growth, a local baseline and vaccination context, and forms bounded groups. It returns transparent factors and states. Closed episodes remain incidence evidence until the active window expires; professional confirmation is preserved through recalculation. Capacity errors are explicit rather than silently truncating evidence.

Reports use a stable client UUID and a unique MongoDB `(reporter_id, client_report_id)` index. Identical retries repair secondary projections and return the original case; a conflicting reuse is rejected. Case workflow mutations use an operation UUID and expected aggregate version for idempotency and optimistic concurrency.

The production PWA caches its versioned application shell. IndexedDB stores user-scoped animal records and reports, including photo/voice blobs, before transmission. It displays “Saved offline — waiting to sync” and “Synced successfully.” Reconnect, startup and a 15-second foreground timer trigger retries. Validation errors need correction; expired sessions retain the report until the same user signs in again. Browser Web Locks serialize tabs, and server UUID constraints provide final duplicate protection. See [offline architecture and recovery](docs/OFFLINE.md).

## Tests and evidence

```powershell
$env:MONGODB_TEST_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.runtime/pytest-check
cd frontend
npm run typecheck
npm run build
```

The final backend gate passed **194 tests**, including real MongoDB radius/time/index and idempotency checks. The production build includes TypeScript checking. Browser evidence under `.runtime/` covers replay/map, farmer → vet → lab → authority → closure, real offline recovery (`phase5-browser.json`), all five mobile/desktop role layouts and Chrome PWA installability. The [evaluation report](docs/EVALUATION.md) explains the actual synthetic model metrics, constructed outbreak scenarios and operational denominators.

## Deployment

Use `backend/Dockerfile` with the repository root as build context, `compose.yaml` for local API + MongoDB, `render.yaml` for the API service, and `frontend/vercel.json` for SPA routing. [Deployment instructions](docs/DEPLOYMENT.md) cover Atlas, environment variables, professional-account provisioning and the production PWA preview. No external hosting account has been deployed to or claimed as connected. Docker is not installed on this workstation, so the container runtime remains unverified; the Python application and production frontend are exercised locally.

## Limitations and future scope

The prototype has no clinical validation, field baseline, weather signal, computer vision model, validated all-language speech recognition, government integration or emergency dispatch. Thresholds and synthetic metrics are evaluation fixtures. It currently requires one API worker because projection coordination uses process locks, and it explicitly rejects surveillance workloads above its documented capacity. Offline data remains on the device until browser data is cleared; use trusted devices. Attachment validation checks format signatures and size, without malware scanning. Future work can add validated datasets, weather adjustment, vaccination reminders, regulatory drafts, One Health flags, validated image assistance, broader language support and external messaging after the hard MVP is field-tested.
