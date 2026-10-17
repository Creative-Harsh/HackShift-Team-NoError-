# PashuRaksha implementation plan

Source: the complete 25-section `PRD_PashuRaksha_SIH26128_Revised.md`, read before implementation. The user's explicit priorities take precedence over conflicting phase/optional labels in the PRD.

## Decisions and contradictions

- Offline reporting and 12-digit identity simulation are mandatory, even though later PRD sections call them optional. Laboratory is a fifth first-class role from Phase 1.
- Use `vet_review` for the professional field-investigation step. Store every transition in a case timeline. A model cannot set confirmation status.
- Public registration creates farmers only. Privileged roles are provisioned by a local seed/admin process; a registration role field cannot grant authority.
- Node is used only for Vite, TypeScript, frontend dependency installation and browser tests. There is no Node backend.
- MongoDB Atlas is the deployment database. A local MongoDB instance can exercise the same PyMongo code and real 2dsphere queries. Mock databases are test-only and never silently replace a failed MongoDB connection.
- No Atlas, Cloudinary or external service credentials are present. Private files use MongoDB GridFS, an object-storage equivalent available with both local MongoDB and Atlas. Files persist in the database, without a separate server disk. No automatic public deployment or government integration is implied.
- Use clearly labelled synthetic training and operational data. Metrics measure this prototype only, not clinical performance. Defer CV, voice transcription, LLM and weather integrations.
- Case confirmation and outbreak confirmation are separate. An authorized authority action with professional evidence is required to confirm an outbreak; lab-positive cases alone do not silently declare an official event.

## Final architecture

React + Vite + TypeScript PWA -> typed Axios REST client -> FastAPI/Pydantic services -> PyMongo -> MongoDB (Atlas/local). Leaflet/OSM renders database-derived cases and clusters; Recharts renders aggregates. React Hook Form + Zod validates forms. IndexedDB stores user-scoped cached animal data and queued reports. A stable client report UUID and unique database constraint make retrying safe.

Backend services separate authentication, EHR, reports, triage, risk, geospatial queries, outbreaks, vet/lab workflow, media and notifications. Deterministic rule/risk/cluster functions accept explicit inputs and timestamps. A scikit-learn classifier has a versioned synthetic training/evaluation pipeline and a rules-only fallback. Generative AI is an optional, disabled adapter with no authority over scores or confirmation.

## Directory structure

```text
PashuRakshak/
  frontend/
    public/                  # manifest, service worker, app icons
    src/
      components/            # controls, badges, map, charts
      features/              # auth, reporting, offline, surveillance
      hooks/
      layouts/
      pages/                 # role-specific working screens
      services/              # typed API client
      types/
    package.json
    vite.config.ts
    vercel.json
  backend/
    app/
      auth/
      database/
      schemas/
      routes/
      services/
      triage/
      risk_engine/
      geospatial/
      outbreak/
      lab/
      notifications/
      main.py
    scripts/                 # seed, incremental outbreak replay
    Dockerfile
    requirements.txt
    .env.example
  ml/                        # synthetic generator, trainer, model card, evaluation
  tests/                     # unit, API, real Mongo integration, browser checks
  docs/
    ARCHITECTURE.md
    DEMO.md
    ML_AND_RISK_ENGINE.md
    OUTBREAK_ENGINE.md
    EVALUATION.md
  IMPLEMENTATION_PLAN.md
  TASKS.md
  README.md
  compose.yaml
```

## Hard MVP and dependency graph

P0 foundation/auth/RBAC -> EHR + structured report persistence -> P1 triage + explained risk -> P2 geospatial + cluster calculation + map -> P3 vet/lab + surveillance -> P4 offline synchronization -> complete demo/evaluation/deployment verification. P5 optional features remain deferred until all gates pass.

Phase gates: after every phase run backend tests, TypeScript checking, frontend production build and a runtime API smoke check. Repair failures before starting the next phase. Test-only mocks do not satisfy the real Mongo geospatial gate.

## Collections and indexes

- `users`: UUID `_id`, name, normalized unique email, Argon2 password hash, role, district, created_at. Never return password hashes.
- `sessions`: JWT jti, user_id, expires_at; unique jti and TTL expiry. Logout revokes server-side session.
- `animals`: UUID, unique 12-digit `pashu_id`, name, species, breed, `age_months`, sex, owner_id/name, GeoJSON location, village/district, vaccination/disease/treatment/lab histories, health_status. Index owner_id, pashu_id, location 2dsphere.
- `disease_cases`: UUID, animal/reporter identity, immutable structured `report`, report UUID (`client_report_id`), report/receipt timestamps, `triage`, `risk`, GeoJSON `location`, animal snapshot, status, confirmation, assigned_vet_id, reviews, timeline. Unique `(reporter_id, client_report_id)`; indexes location 2dsphere, animal_id, reported_at, disease, status/risk. Embedded report/triage/risk provide an atomic initial write instead of inconsistent separate projections.
- `lab_tests`: case_id, requested_by, test_type, sample status, result and attachment metadata; index case_id/status. Case transitions use atomic conditional updates and reconciliation when multi-document transactions are unavailable locally.
- `outbreak_clusters`: stable cluster identity, case_ids, center, disease, period, score/factors, state, professional confirmation evidence; 2dsphere center index.
- `notifications`: recipient or authorized role/district, case/cluster reference, message, created_at, read state. Unique event key prevents repeated alerts.
- `audit_logs`: actor, action, resource, timestamp, details. Sensitive credential/report contents excluded.
- `demo_runs`: scoped replay progress and scenario identifiers; seed/replay must be idempotent and explicitly enabled.

All dates are UTC ISO-8601 in API JSON and timezone-aware database dates. GeoJSON order is longitude, latitude. Clinical event time and server receipt time are distinct; future report timestamps are rejected.

## Phase 1 API contracts (shared frontend/backend contract)

Prefix `/api`. IDs are strings. Successes return JSON; errors use FastAPI `detail`. List endpoints return arrays unless stated otherwise. All protected requests use `Authorization: Bearer <access_token>`.

- `GET /health` -> `{status, database, demo_mode}` (503 if database unavailable).
- `POST /auth/register` `{name,email,password,district}` -> `{access_token,token_type,user}`. Role always `farmer`.
- `POST /auth/login` `{email,password}` -> `{access_token,token_type,user}`. User `{id,name,email,role,district}`; roles `farmer|paravet|vet|lab|admin`.
- `POST /auth/logout` -> `{message}`; `GET /auth/me` -> user.
- `GET /animals` -> scoped `Animal[]`; `GET /animals/pashu-id/{pashu_id}` -> scoped Animal; `GET /animals/{id}` -> Animal.
- `POST /animals` and `PUT /animals/{id}` -> Animal. Input `{name,pashu_id?,species,breed,age_months,gender,owner_id?,location:{type:'Point',coordinates:[lon,lat]},village,district}`. Allowed species `cattle|buffalo|goat|sheep|pig`, gender `female|male`. Omitted pashu_id is generated. Farmer owns its animals. Paravet creates records for a farmer in its district.
- Animal output additionally `{id,owner_id,owner_name,pashu_id,vaccination_history:[],disease_history:[],treatment_history:[],lab_history:[],health_status,created_at}`.
- `GET /animals/{id}/history` -> `{animal,cases,lab_tests}`.
- `POST /animals/{id}/vaccinations` -> Animal; `{vaccine,date_given,next_due_date}` restricted to paravet/vet.
- `POST /reports` -> Case (201 new; same logical case for retry). Input `{client_report_id:UUID,animal_id,symptoms:string[],temperature_c?:number,appetite:'normal'|'reduced'|'none',milk_drop_percent:0..100,activity:'normal'|'reduced'|'recumbent',recent_contact:boolean,vaccination_status:'up_to_date'|'overdue'|'unknown',mortality_count:0..1000,duration_hours:0..2160,location:Point,reported_at?:ISO,image_url?:string,voice_note_url?:string}`.
- Symptom keys `fever,cough,nasal_discharge,drooling,skin_lesions,mouth_foot_lesions,diarrhea,weakness,swelling`.
- `GET /cases` -> scoped Case[]; `GET /cases/{id}` -> Case. Case fields `{id,animal_id,animal_name,pashu_id,species,village,district,reporter_id,report,location,reported_at,created_at,updated_at,status,confirmation_status,triage:null|object,risk:null|object,timeline:[],assigned_vet_id:null|string}`.
- `GET /users/farmers` -> `{id,name,email}[]` for district paravet/admin; used for correct EHR ownership.

## Later-phase API contracts

- Triage `{suspected_disease,probability,severity,triggered_rules:string[],missing_information:string[],recommended_escalation,model_version,model_source}`.
- Risk `{score,level,factors:[{key,label,points,detail}],version}`. Factor sum equals score. Bands LOW 0-29, MODERATE 30-59, HIGH 60-79, CRITICAL 80-100.
- `GET /cases/nearby?longitude=&latitude=&radius_km=&days=&disease=` returns scoped recent cases using Mongo `$near`.
- `GET /outbreaks`, `GET /outbreaks/map` (cases/clusters), `GET /outbreaks/{id}`, `POST /outbreaks/recalculate`, `POST /outbreaks/{id}/confirm` with evidence/note. Professional roles only for detailed map; admin confirms with lab evidence.
- `POST /cases/{id}/assign-vet` `{vet_id?}`; `PUT /cases/{id}/vet-review` `{diagnosis,recommendations}`; `POST /cases/{id}/request-lab` `{test_type,notes}`; `PUT /cases/{id}/status` `{status,note}` with explicit transition graph.
- `GET /lab/requests`; `PUT /lab/tests/{id}` `{status:'received'|'testing'|'positive'|'negative'|'inconclusive',result_notes?,confirmed_disease?,attachment_url?}`.
- `GET /admin/dashboard`, `/admin/analytics`, `/admin/audit`, `/evaluation`, `/notifications` return database-derived state and measured prototype metrics.
- `POST /media` multipart file -> private attachment metadata/URL; authorized authenticated retrieval. Local persistent storage for development; optional Cloudinary adapter for deployment.
- `POST /demo/replay` admin-only, demo mode only, incrementally creates actual reports. Never hardcode dashboard outcomes.

## Phases

1. Foundation: repository/configuration, database connection/indexes, secure auth/RBAC, all roles, seed accounts, EHR + lookup/history, structured report storage, responsive role-aware frontend, tests and build.
2. Intelligence: documented synthetic training pipeline, held-out evaluation, rule engine, context/history-aware deterministic risk, factor explanations and detail UI.
3. Outbreak: real Mongo spatial queries, disease/symptom and time-bounded clustering, local baseline/growth/vaccination score, marker/cluster/density map with filters, deterministic scenarios and replay.
4. Response: assignment/review, lab lifecycle and evidence, guarded confirmation/state graph, in-app notifications, live admin aggregates/charts and operational metrics.
5. Offline and delivery: PWA app shell, IndexedDB cached animals and per-user queue, stable UUID deduplication, retry/error states, reconnect sync, offline browser checks, full demo, docs and Docker/Vercel/Render configuration.

## Risks and testing

- Synthetic model scores are not calibrated clinical probabilities; publish data provenance and actual held-out metrics. Unknown patterns must not force a diagnosis. No medication/dosage generation.
- Outbreak thresholds/baselines are prototype configuration, not validated epidemiology. Spatial chains must not merge unlimited distances. Repeated reports for the same animal must not inflate distinct-animal cluster size. Inactive/old/rejected cases and future timestamps need explicit handling.
- Authorization must protect object ownership, district scope, media and offline account changes, not just route navigation. Privileged registration, direct-object access, forged tokens, revoked sessions and invalid transitions need negative tests.
- Sync retries can race or follow an ambiguous network failure; enforce idempotency in Mongo and reject conflicting reuse of a report UUID.
- Atlas/network/tile availability and browser service-worker lifecycle require honest UI failures; shell/report queue should work without map tiles. No production fallback to mocks.
- Test pure deterministic factors, exact score sums/boundaries, A distant/B stale/C similar active/D rapid concentrated clusters, baseline-sensitive scores, duplicate-animal resistance, API auth/RBAC, clinical states, lab reconciliation and notification generation. Exercise real Mongo `$near` separately from unit tests.
- Full role-by-role runtime demo and browser tests cover create/lookup/report/triage/map/vet/lab/admin and offline reconnect without duplicate cases. Record only measured evaluation values and any unverified limits.
