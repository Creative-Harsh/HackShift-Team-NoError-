# PashuMitra implementation

The existing React/Vite/TypeScript app, FastAPI/PyMongo API, JWT/RBAC, rules/RF risk service, five-role workflow and IndexedDB reporting remain authoritative. `POST /api/triage` is a non-saving assessment, but requires a complete report. At the initial audit, the language service had only a disabled adapter and no speech implementation. The completed feature is documented in PASHUMITRA.md.

## Design

- A JSON catalogue defines stable guide IDs, translations, roles, help intents and status descriptions. It is shared by frontend and backend. Only registered targets may receive an inert overlay.
- The assistant renderer can highlight, position its SVG calf and speak plain text. It has no navigation, click, form-writing, queue-writing or record-mutation capability. User interaction with the underlying app remains unchanged.
- Typed local help works offline. Optional Gemini intent extraction uses a bounded backend adapter, explicit provider consent and sanitized text. No provider-generated medical/status prose is rendered.
- Symptom candidates preserve negation, severity and duration. They are read back and explicitly verified in assistant-only session memory. Incomplete observations stay unknown. Existing rule evaluation supplies urgency, never an LLM; incomplete conversations do not produce fabricated risk scores.
- Page-context consent is separate from microphone/provider consent. Context consists of an allowlisted page key and target IDs; current-case status is retrieved through existing backend authorization. No screenshot/DOM text/form values are sent to a provider.
- Speech uses feature-detected browser recognition and synthesis with language selection, text fallback and clear remote-processing disclosure. Voice availability is a device/browser capability, not an offline guarantee.
- Logout, identity changes, dismissal, visibility changes and stale async replies are handled explicitly. Symptoms are linked to an assistant-selected animal and cleared on animal changes. No transcript/audio is persisted by the app.

## Files

New backend: `app/assistant/{catalog.json,schemas.py,service.py,provider.py}`, `routes/assistant.py`.
New frontend: `features/assistant/{catalog,conversation,registry,useVoice,PashuMitra,Mascot}` and scoped CSS; guide markers added to existing controls.
Tests: assistant API and deterministic extraction tests; Chrome guidance/permissions/lifecycle tests; existing regression suite.
Docs: PashuMitra usage, privacy, environment variables, measured language/browser limitations and demo instructions.

## Checkpoints

- [x] Shared catalogue, local text intents, guide registry, inert mascot/highlight and role integration.
- [x] Typed assistant API, verified symptoms, rule-only urgency with missing data disclosed, optional provider boundary.
- [x] Build/type/backend gate for guidance and assistant service.
- [x] Click-activated speech, transcript, mute, language selection and privacy/lifecycle controls.
- [x] Browser tests: no business actions, no unconsented page access, role/animal/account isolation, unavailable voice/provider, offscreen/mobile targets, reduced motion.
- [x] Final production build, regression tests, browser demo and documentation.

Camera capture is optional and deferred until these checkpoints pass. No clinical model, record workflow or government integration changes are included.
