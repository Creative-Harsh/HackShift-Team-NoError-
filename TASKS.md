
# PashuRaksha task checklist

## Planning
- [x] Read the complete PRD and inspect the workspace.
- [x] Resolve priority contradictions and document decisions.
- [x] Create implementation plan, architecture, collection contracts and tests.

## Phase 1 — Foundation
- [x] FastAPI configuration, Mongo connection, startup indexes and health check.
- [x] JWT authentication, Argon2 hashing, revocation and role/district RBAC.
- [x] Seed labelled demo accounts, villages, animals, histories and simulated IDs.
- [x] Animal create/edit/list/detail, Pashu ID lookup and history.
- [x] Structured validated GeoJSON reports with stable UUID idempotency.
- [x] React/Vite/TypeScript shell, auth, EHR and farmer report screens.
- [x] Phase 1 backend, frontend build and browser gate.

## Phase 2 — Triage and risk
- [x] Versioned synthetic data generator, Random Forest artifact and model card.
- [x] Deterministic rule triage with species gates, missing data and safe actions.
- [x] Explainable risk score with exact factor breakdown and vaccination/history context.
- [x] Adversarial classifier fallback and report boundary tests.
- [x] Phase 2 gate: 113 backend checks, TypeScript/build and farmer browser evidence.

## Phase 3 — Outbreak intelligence
- [x] Real Mongo `$near`, GeoJSON `2dsphere` indexes and future-safe time windows.
- [x] Latest-animal deduplication, distance/time/disease/symptom similarity and bounded groups.
- [x] Growth, local baseline and vaccination score factors with isolated/abnormal/suspected/confirmed states.
- [x] Incremental persisted synthetic replay and admin-only controls.
- [x] Leaflet markers, zoom grouping, risk-weighted density, filters and hotspot evidence.
- [x] Scenarios A/B/C/D, stale/future/rejected tests and measured outbreak evaluation.
- [x] Gate: 163 backend tests (including real Mongo) and `phase3-browser.json`.

## Phase 4 — Professional response
- [x] High-risk veterinarian queue, assignment, review and professional recommendations.
- [x] Versioned transition graph with operation UUIDs and idempotent retries.
- [x] Sample request, receipt, testing, positive/negative/inconclusive outcomes.
- [x] Case/EHR/lab projections, audit records, notifications and interrupted-write repair.
- [x] Explicit admin outbreak confirmation requiring matching positive laboratory evidence.
- [x] Database-derived admin KPIs, charts, critical list and operational timing.
- [x] Private authenticated media upload/download with MIME/signature and size checks.
- [x] Gate: seven workflow tests, adversarial checks, frontend build and `phase4-browser.json`.

## Phase 5 — Offline and delivery
- [x] Installable PWA manifest and shell service worker; private API responses are never cached.
- [x] Per-user IndexedDB animal cache and stable-UUID report queue with committed writes.
- [x] Reconnect/startup synchronization, cross-tab lock, bounded retries and blocked 4xx state.
- [x] Account-bound token checks and server-side duplicate protection.
- [x] `.env.example`, Vercel configuration, Render blueprint and deployment documentation.
- [x] Dockerfile, Compose file, non-root API image definition and private professional-account provisioning command.
- [x] Actual Chrome disconnect/reload/reconnect with photo bytes verified in GridFS and exactly one case per report UUID.
- [x] Expired-session recovery and switching farmer accounts without cross-account synchronization.
- [x] PWA installability check in a persistent Chrome profile, with no installability errors.
- [x] Mobile/desktop layouts of all five roles, including repair of a hidden-label table overflow.
- [x] Final backend gate: 178 passed, including real MongoDB; TypeScript and production build passed.
- [x] Final fresh-data map resize/replay and professional care walkthrough after the last integration fixes.

## External deployment verification (not claimed as completed)
- [ ] Build and start the Docker image on a machine with Docker installed.
- [ ] Configure private Atlas/Render/Vercel accounts and verify an external HTTPS deployment.

## Optional future scope
- [ ] Validated field dataset and clinical model evaluation.
- [ ] Weather adjustment, vaccination reminders, regulatory drafts and One Health flags.
- [ ] Validated image model, broad multilingual symptom extraction, WhatsApp and IVR.

## Optional PashuMitra companion — implemented after the hard MVP
- [x] Shared finite guide catalogue, role/page checks and real `data-guide` targets.
- [x] Click-activated SVG calf, responsive panel, read-only highlight and manual navigation guidance.
- [x] English/Hindi/Hinglish text help, negation, uncertainty, duration, verified observations and follow-up memory.
- [x] Existing-rule concern checks, missing information and authorized current-case status; no record mutations.
- [x] Separate page, browser-speech and optional Gemini consents; bounded backend intent adapter with no-key fallback.
- [x] Microphone/TTS controls, transcript, text fallback, 20-second cutoff, stop/mute and stale-result cancellation.
- [x] Account/animal isolation, payload-free report-selector invalidation, close/reset and reduced motion.
- [x] Sixteen assistant backend checks; full gate 194 passed including real MongoDB.
- [x] Ten Playwright language/browser scenarios; unchanged forms, routes, queues and database state verified.
- [x] TypeScript/production build and usage/privacy/deployment documentation in `docs/PASHUMITRA.md`.
- [ ] Presentation-device acoustic recognition/pronunciation and optional live Gemini-key check (provider/hardware dependent).

## Verification log
- PashuMitra: 194 backend tests passed with no failures/skips in 140.69s (`.runtime/mitra-full-tests.xml`); 10 browser/language scenarios passed. Speech recognition/synthesis lifecycle uses deterministic browser mocks, not measured acoustic accuracy. Core reporting remains independent of the companion and any model key.
- Phase 3: 163 tests passed in 218.73s; real Mongo radius/time/disease/future exclusion checks included. Clean Chrome replay/map browser smoke passed with no runtime/API errors; report saved in `.runtime/phase3-browser.json`.
- Phase 4: seven workflow tests passed in 21.23s; adversarial classifier fallback 11 tests passed. Clean Chrome farmer → vet → lab → authority → treatment/closure smoke passed with no runtime errors; report saved in `.runtime/phase4-browser.json`.
- Frontend production build passed after PWA/offline integration (Vite 7.3.6; TypeScript compile included). Zod/Rollup annotation warnings are dependency warnings only.
- Final backend gate (13 September): 178 passed, zero failures/skips, in 320.26s; `.runtime/final-tests.xml`. Actual local MongoDB was enabled for both integration tests.
- Offline browser gate: two queued reports synced, persisted photo bytes matched, duplicate retry returned the original case, expired-token and account-switch recovery passed; `.runtime/phase5-browser.json`.
- Chrome PWA installability passed in a persistent profile; `.runtime/install-browser.json`. Incognito contexts used by other browser tests intentionally cannot install PWAs.
- Role layout gate: all five workspaces at 390px and 1440px, no page overflow or uncaught runtime errors; `.runtime/layout-browser.json`.
- Final map rerun: 11 actual replay reports; first two isolated, three animals score 64 (abnormal), five score 67 (suspected), final 11-animal cluster score 71. GeoJSON, all seven factors, filters, marker grouping, density toggles, zero-size resize recovery and mobile layout passed with no API/runtime errors; `.runtime/phase3-browser.json`.
- Final care rerun: online farmer submission → vet claim/review → sample → received/testing → positive result → explicit district confirmation → veterinary control action → closed case, all through Chrome and real MongoDB; `.runtime/phase4-browser.json`, no runtime errors.
- Final ID lookup/report rerun: simulated ID 261280000001 loaded, Possible LSD/risk 76 displayed with an exact factor sum, desktop/mobile checks passed; `.runtime/phase2-browser.json`.
