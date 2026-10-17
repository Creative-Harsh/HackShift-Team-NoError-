# Prototype evaluation

All disease examples, outbreak scenarios and seeded operational records are synthetic. No metric below establishes clinical performance, field outbreak sensitivity or government-system connectivity.

## Disease classifier

Source: `ml/evaluation.json`, reproduced by `python -m ml.train`. Training uses 4,000 synthetic examples with seed 26128; evaluation uses 1,200 held-out synthetic examples with seed 26129. The pipeline checks zero exact feature-vector overlap. Both samples still share a generator, which limits the meaning of the results.

| Metric | Calculated value |
| --- | ---: |
| Accuracy | 0.856667 |
| Macro precision | 0.851343 |
| Macro recall | 0.856667 |
| Macro F1 | 0.852178 |

The artifact includes per-class metrics, confusion matrix, sample counts and data hashes. These values describe the Random Forest alone on the synthetic distribution. They do not validate the complete rule-constrained workflow or calibrate class scores as medical probabilities. Symptom/species rules still gate hypotheses; missing, incompatible or corrupt models fall back to rules without invented probabilities.

## Outbreak engine

Source: `ml/outbreak_evaluation.json`, reproduced by `python -m ml.evaluate_outbreak`. These are eight designed scenarios with known intended behavior.

| Scenario | Calculated behavior |
| --- | --- |
| A: six geographically distant reports | No cluster |
| B: six nearby reports months apart | No active cluster |
| C: six similar recent nearby animals | One suspected cluster, score 66, HIGH intensity |
| D: eleven concentrated reports with rapid increase | One suspected cluster, score 95, CRITICAL intensity |
| Twelve reports of one animal | No cluster; distinct-animal deduplication |
| Six future observations | No cluster |
| Six reports with insufficient symptom agreement | No cluster |
| Six unrelated disease categories | No cluster |

The six designed negative scenarios produce 0 alerts (0/6); both positives produce clusters (2/2). These tiny constructed denominators cannot estimate field false-alert or missed-outbreak rates. Holding six active observations constant, a dense historical baseline reduces score from 66 to 53, demonstrating the contribution of baseline context.

In the fixed chronological replay, the first abnormal alert occurs 12 hours after the first report. It precedes a toy comparator that triggers on the sixth distinct similar local animal by 18 hours; the first suspected state precedes that comparator by 6 hours. This compares two mechanisms on one known synthetic replay, not disease onset or actual veterinary detection. Calculation milliseconds in the JSON measure only local engine execution, excluding network and field response time.

## Operational and offline measures

The admin dashboard calculates mean report-receipt → first-vet-assignment minutes from `created_at` and `assigned_at`, with denominator `assigned_case_count`. With no assignments it returns `null`, displayed as unavailable. Unresolved critical cases come from unclosed database records with CRITICAL risk. Cases-over-time and disease/species/risk charts use the last 30 days of observations; workload KPIs describe current records.

Each farmer/paravet synchronization panel counts actual queued reports and successful syncs from IndexedDB rows for that account and device. Counts persist across reloads; they are not fleet-wide metrics. `tests/browser-offline.cjs` checks durable offline reload, actual photo-byte persistence, duplicate prevention, expired-session recovery and account isolation, writing evidence to `.runtime/phase5-browser.json`.

## Engineering verification

The final backend regression on 13 September 2026 passed **178 tests**, including two opt-in tests against real MongoDB. It covers authentication, ownership/district RBAC, EHR, report idempotency, validation, model fallback, exact risk totals, spatial queries/indexes, cluster scenarios, stale/future/rejected observations, workflow versions/retries, laboratory evidence and private attachments. Source: `.runtime/final-tests.xml`. Dependency deprecation warnings remain; this gate had no failures or skipped tests.

The frontend gate checks TypeScript and Vite production bundling. Browser scripts cover simulated ID → report → assessment, outbreak replay/map, farmer → vet → lab → authority → closure, offline recovery, and mobile/desktop role layouts. See `TASKS.md` for completed browser gates and `.runtime` evidence. Docker is unavailable on this workstation, so container startup and external Atlas/Render/Vercel deployment remain untested. Those limitations are separate from the locally verified API, MongoDB and browser flows.
