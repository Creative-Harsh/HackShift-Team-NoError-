# Disease triage and explainable risk

PashuRaksha computes preliminary assessments from structured observations and EHR context. No LLM, external AI API, weather API or government dataset participates in these calculations. The classifier, rule engine and priority score cannot confirm a disease or an outbreak.

## Implemented interfaces

`app.triage.assess(report, animal, now)` consumes the immutable structured report, an animal EHR snapshot and a timezone-aware observation time. It returns `suspected_disease`, `disease_code`, nullable `probability`, `probability_kind`, `severity`, `triggered_rules`, `rule_strength`, `missing_information`, `recommended_escalation`, `model_version`, `model_source`, `safe_actions` and `assessment_notice`. Severity is low, moderate, high or critical. No function writes to MongoDB or requires a network request.

`app.risk_engine.calculate_risk(report, animal, triage, nearby_count=0, cluster_score=0, now=None)` returns `score`, `level`, `factors` and `version`. Every factor has a stable key, label, integer points and a detail derived from the inputs. Factor points sum exactly to the score. The report service embeds the assessment and risk in its case document; later spatial calculation can supply actual context values.

## Rules and uncertainty

The prototype has two specific disease hypotheses and three broad categories:

| Category | Required observations and boundaries |
| --- | --- |
| Possible Lumpy Skin Disease | Skin lesions in cattle/water buffalo. Evidence strength: skin 0.60 + fever 0.25 + swelling 0.15. |
| Possible Foot and Mouth Disease | Mouth/foot lesions in a supported cloven-hoof species. Strength: lesions 0.65 + drooling 0.20 + fever 0.15. |
| Possible respiratory syndrome | Cough 0.55 + nasal discharge 0.20 + fever 0.15 + weakness 0.10. No specific cause claimed. |
| Possible gastrointestinal syndrome | Diarrhea 0.60 + weakness 0.20 + appetite change 0.20. No specific cause claimed. |
| Undifferentiated illness | Insufficient, unsupported or conflicting observations; professional assessment needed. This is not a healthy clearance. |

A measured temperature at or above 39.5 C adds a fever observation. This is a deliberately broad prototype alert threshold, not a species-specific diagnostic definition. Skin findings on goats, sheep or pigs cannot produce an LSD suggestion. A classifier output alone cannot bypass required symptom/species rules. Two strong overlapping patterns within 0.10 remain undifferentiated. A strong rule pattern may remain a hypothesis even if the classifier disagrees, with disagreement explicitly listed for veterinary review.

Reported mortality or inability to stand sets critical clinical severity regardless of model output. Mouth/foot lesions, a strong pattern, no appetite or a measured temperature at or above the prototype 41 C severe-observation threshold trigger high clinical severity. These are unvalidated prioritization heuristics. Veterinary examination and laboratory evidence remain separate workflow steps.

The symptom vocabulary and species boundaries were checked against [WOAH lumpy skin disease](https://www.woah.org/en/disease/lumpy-skin-disease/) and [WOAH foot and mouth disease](https://www.woah.org/en/disease/foot-and-mouth-disease/). WOAH describes bovine LSD with fever, skin nodules and swelling; FMD includes vesicular mouth/foot findings and requires laboratory differentiation from other vesicular diseases. Those references do not validate this prototype's numerical weights, severity thresholds or classifier.

## Synthetic classifier and measured evaluation

The checked-in RandomForest artifact is built by `ml/train.py` from `ml/synthetic.py`. All 4,000 training rows and 1,200 held-out rows are synthetic. Latent labels precede noisy/overlapping symptom sampling, temperatures may be missing or contradictory, and EHR vaccine types are sampled independently of target disease subject to species eligibility. No patient, government or laboratory training data is used. Distinct fixed seeds generate train/test sets, and the training script verifies zero exact feature-vector overlap.

The shared 28-feature transform includes symptoms, species, measurements, age, contact/movement, mortality, duration, relevant vaccine gaps and recent dated disease history. The RandomForest uses 180 trees, maximum depth 12, minimum leaf size 4, balanced-subsample class weights and fixed seed 26128. The checked-in dependency lock fixes the scikit-learn runtime. See [scikit-learn RandomForest documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html) for the algorithm interface.

Final measured held-out classifier results from `ml/evaluation.json`:

| Metric | Value |
| --- | ---: |
| Accuracy | 0.856667 |
| Macro precision | 0.851343 |
| Macro recall | 0.856667 |
| Macro F1 | 0.852178 |
| Train/test feature-vector overlap | 0 |

The JSON includes per-class metrics, confusion matrix, data hashes, seeds and evaluation scope. These are synthetic classifier metrics, **not clinical performance or validation of the complete triage pipeline**. Separate random samples still share a generator and cannot establish generalization to real farms. Metric definitions use the [scikit-learn evaluation reference](https://scikit-learn.org/stable/modules/model_evaluation.html).

`probability` is the selected category's raw RandomForest class score, labelled `uncalibrated_synthetic_model_score`. It is not a clinical probability. A trusted local artifact and metadata are loaded with schema, runtime-version and SHA256 checks. Missing, incompatible or corrupt artifacts fall back to deterministic rules, publish `probability: null`, and do not invent substitute probabilities. API startup never retrains or downloads a model. Reproduce artifacts with `.venv\Scripts\python.exe -m ml.train` from the repository root.

## Exact risk formula

`risk-v1` is a bounded operational priority index. All arithmetic is deterministic, with half-up rounding for individual contributions.

| Factor | Maximum | Calculation |
| --- | ---: | --- |
| Symptom/acute evidence | 28 | 28 x maximum rule strength. Inability to stand or temperature >=41 C establishes a minimum strength of 0.85; no appetite establishes 0.50. Acute floors are disclosed in the factor detail. |
| Synthetic classifier support | 12 | 12 x selected specific category score. Zero for rules-only or undifferentiated output. |
| Mortality | 15 | 15 if one or more herd deaths are reported; otherwise zero. |
| Relevant vaccination gap | 12 | Overdue 12; unknown 6; current/not-applicable 0. |
| Vulnerability/recent history | 8 | Age below 12 months: 8; age >=120 months: 4; a dated disease episode in preceding 90 days: +4; cap 8. |
| Recent contact/movement | 5 | 5 if reported, otherwise zero. |
| Nearby similar episodes | 12 | 2 per nearby similar distinct-animal episode, capped at 12. |
| Cluster strength | 8 | 8 x cluster score / 100, capped at 8. |

The maxima sum to 100. Default bands are LOW 0-29, MODERATE 30-59, HIGH 60-79 and CRITICAL 80-100. `risk_level` accepts validated custom increasing thresholds; changing defaults must be reviewed and versioned. There is no fabricated weather contribution. Before spatial context is calculated, nearby and cluster contributions are zero and explicitly described as such.

Vaccination is disease-specific: an FMD record cannot establish LSD vaccination. The newest valid matching dose on or before observation time is used. Doses after observation time and invalid due dates are ignored; a later valid dose supersedes older overdue records. A conflicting self-report cannot cancel overdue EHR evidence, and self-reported overdue status is retained for verification. Broad syndromes without a specific vaccine mapping receive no vaccine points. Disease history must be dated within the 90 days preceding observation, so future entries cannot increase retrospective risk.

Clinical urgency and numeric population-context risk are deliberately distinct. Mortality alone can yield a numerically low additive score while clinical severity is critical. Callers must prioritize HIGH/CRITICAL risk **or high/critical clinical severity**, and always display the escalation recommendation. A low score does not mean an animal is safe. Scores are prototype heuristics, not validated epidemiological or veterinary instruments.

## Safety and verification

Safe actions are fixed, reviewable text about veterinary contact, monitoring, hygiene and appropriate separation/movement precautions. Mortality advice directs people away from carcasses to professional handling instructions. No medication or dosage is suggested. Confirmation fields are absent from both calculation APIs.

`tests/test_intelligence.py` covers species exclusions, unknown/overlapping patterns, model provenance, rules fallback, urgency, severe measurements, dated vaccine/history context, exact budgets, score boundaries, monotonic spatial factors, reproducibility and immutable input behavior. Independent adversarial/API tests exercise malformed model artifacts and case integration. Future work requires veterinarian-reviewed datasets, external-site/time validation, calibration and clinical review of all thresholds.
