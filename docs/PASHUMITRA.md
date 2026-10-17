# PashuMitra companion

PashuMitra is an optional livestock mascot at the bottom right of each authenticated workspace. It explains the website, points to actual controls and checks verified conversational observations against the existing deterministic rules. It does not determine a diagnosis, prescribe treatment, confirm outbreaks or operate the application for the user.

## Try it

1. Sign in as **Farmer** and click the calf. It starts in text mode. Choose **English**, **हिन्दी** or **Hinglish**.
2. Type `Meri gaay ko bukhar hai aur khana nahi kha rahi do din se`, or enable browser speech processing and press **Talk**. For Hindi/Hinglish recognition, select that language before speaking. Press the speaker to enable spoken replies.
3. Review the extracted observations: fever, not eating, 48 hours. Missing measurements remain unknown. A follow-up adds information; an explicit correction replaces that observation. Contradictory/uncertain descriptions need clarification.
4. Enable **Allow current-page guidance**, explicitly load your authorized animals, choose Gauri (`261280000001`) and verify the observations. The existing rule engine flags no appetite for urgent professional attention. The assistant neither calculates an incomplete risk score nor creates a case.
5. Ask `Report kaise banau?`. The calf points to **Report symptoms**. On a small screen it first highlights **Open menu**. You open the menu and follow the link yourself. Each verified observation has a **Show** control pointing to its corresponding checkbox or field. For no appetite, use the **Appetite** dropdown; do not invent an appetite checkbox. Recheck the animal selected in the actual report. Changing that selection clears the assistant's old symptom context.
6. Complete and submit the actual form yourself. Its normal triage/risk/outbreak workflow remains authoritative. On a case-detail page ask `my report status`; the answer uses that authorized case's current backend state. General questions such as `What does lab pending mean?` explain the state without claiming it is the current report's state.
7. **Minimize** or Escape stops listening/speaking and hides the panel while retaining this session. **Close and clear** discards the conversation and all consents. Logout and account changes also discard it. Choosing a different animal or opening an animal record clears previous observations. No transcripts or audio are persisted by PashuRaksha.

Guide overlays are inert: they do not intercept the highlighted control. The panel folds away during guidance and returns with **Back to chat**. Offscreen controls produce manual scrolling instructions; the assistant never scrolls, focuses, clicks, navigates or fills controls. Animations respect reduced-motion settings.

## Three separate permissions

| Permission | What it permits | What is sent |
| --- | --- | --- |
| Current-page guidance | Inspect only registered target rectangles; read authorized animal options after the load button; retrieve current case status on request | API receives an allowlisted page key, visible target IDs and, for the selected case page, its ID. No screenshots, DOM dump or form values. Animal ID and verified observations are sent only to the application's non-saving concern endpoint. |
| Browser speech processing | A microphone session only after pressing Talk; remote synthesis voices when available | The browser speech service may process audio/transcribed or spoken text externally. Local synthesis voices are preferred. This is independent of Gemini. |
| External language understanding | Optional interpretation of an otherwise unrecognized website-help question | A bounded, sanitized question goes to Google Gemini. No animal records, page context or conversation history is included. Common identifiers are removed, but free text is not guaranteed anonymous. |

The microphone stops after one recognition result, at 20 seconds, on explicit Stop, dismissal, page change, language/consent change, backgrounding or logout. Stale microphone and API results are discarded. There is no wake word or automatic restart. The browser still controls its native microphone permission.

## Implementation and contracts

`backend/app/assistant/catalog.json` is the single catalogue for stable guide IDs, roles, page availability, fallback targets, phrase patterns and controlled translations. React imports the same JSON. Existing components expose `data-guide` attributes. The read-only registry can only locate an allowlisted target and calculate an inert highlight/mascot position. It validates role, page and consent before querying a guide target. Missing and hidden targets resolve to actual available parent controls, or a clear unavailable message.

The companion client exposes narrowly scoped reads and two non-saving POSTs. It has no business mutation API, queue writer, route navigator, DOM click/focus/scroll method or form setter. Model output never carries CSS selectors, URLs, executable actions or spoken medical text. React renders transcript strings as text, not HTML.

| API | Input / behavior |
| --- | --- |
| `GET /api/assistant/capabilities` | Authenticated availability/languages; returns an empty record-mutation tool list. |
| `POST /api/assistant/message` | `text`, `language`, `external_consent`, optional `{page, targets, case_id}`. Returns a finite intent/target/message key and an authorized current-case status where requested. Invalid page/role targets are rejected. |
| `POST /api/assistant/concern` | `animal_id`, partial `observations`, literal boolean `verified: true`. Farmer/paravet/vet/admin only; existing animal authorization applies. Returns `urgent`, `attention` or `insufficient`, actual rule evidence, missing information, `risk_score: null`, `saved: false`. |

Optional observations include explicit true/false/unknown symptom concepts, appetite, activity, measured Celsius temperature, duration and mortality. No complete `ReportInput` is fabricated. The existing rule engine determines concern; the Random Forest and risk engine continue to run through the normal structured report submission. No description is declared "normal" from an incomplete conversation. All assistant POSTs are bounded to 30 requests per user per minute and never persist application records.

`useVoice.ts` owns recognition, synthesis, cancellation and stale-event guards. `conversation.ts` owns conservative extraction and session merging. `registry.ts` owns guide geometry. `PashuMitra.tsx` owns only assistant state. A record-selector change emits a payload-free invalidation event; the companion does not inspect the selected form value.

## Optional Gemini configuration

Leave `GEMINI_API_KEY` and `GEMINI_MODEL` empty for the working no-key mode. To enable the optional backend adapter, set both privately in `backend/.env` or server secrets and restart FastAPI. Choose an available model supporting JSON structured output. Never use `VITE_*` for a secret. The consent checkbox appears when both are configured; this indicates configuration, not a verified provider connection.

The adapter uses the [Gemini generateContent REST contract](https://ai.google.dev/api/generate-content), a fixed Google host, an 8-second timeout and a finite Pydantic intent/evidence schema. Exact evidence, role and target validation apply after parsing. No tools are supplied. Provider failures, unsupported output or missing configuration retain local help. The configured provider was tested with HTTP fixtures; no live key was supplied or live-model performance measured.

## Verified scope and limits

- The full backend gate passed **194 tests**, including real MongoDB integration. Sixteen assistant checks cover authorization, strict contracts, no database mutation, actual case state, partial observations, animal ownership, opt-in and provider contract failures.
- Ten Playwright scenarios passed: multilingual extraction/negation/follow-up memory, finite roles and routes; desktop no-consent/no-mutation/no-queue-change; mobile menu/reduced motion/account isolation; explicit microphone lifecycle with 20-second cutoff and background cancellation; unavailable speech/offline help/invalid model output; real report status and delayed-response dismissal. Browser speech events are mocked deterministically; these tests do not measure acoustic recognition or speaker quality.
- TypeScript and the Vite production build passed. Screenshots and traces are local artifacts in `.runtime/screenshots` and `.runtime/assistant-browser`; full backend evidence is `.runtime/mitra-full-tests.xml`.
- English, Hindi and common Hinglish phrases are a bounded prototype vocabulary, not all-language understanding. The optional model currently expands website-help intent recognition only. Symptom extraction is deterministic and may miss complex phrasing. Review the readback and correct it before using the form.
- [Browser SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) has limited availability and can require server processing. Offline speech is not promised. [Synthesis voices](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/getVoices) depend on the device. If the selected language has no permitted voice, use the transcript or enable the disclosed speech service and retry. Test microphone permission, pronunciation and recognition on the actual SIH presentation device before presenting.
- Transcript, concern checks and guidance continue without a Gemini key. Offline mode supports local text help and cached animal options; fresh concern/status requests need the API. Neither a report nor an offline report is created by the companion.
- Camera-based image interpretation, broad multilingual symptom extraction, remote voice providers and clinical validation remain future scope. No real veterinarian availability, government integration or laboratory connectivity is implied.

Run with MongoDB, API :8000 and production preview :4173 active:

```powershell
cd frontend
npm run build
npm run test:assistant
```
