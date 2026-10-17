# PashuRaksha synthetic classifier v1

This is a hackathon decision-support prototype, **not a clinically validated model**. Every training and test row is synthetic. No government data, farmer patient records or laboratory training data were used. The generator is executable in `ml/synthetic.py`; each symptom frequency, measurement distribution and missingness parameter is visible there.

The five output categories are possible lumpy skin disease, possible foot and mouth disease, respiratory syndrome, gastrointestinal syndrome and undifferentiated illness. The latter categories describe observations without claiming an infectious cause. Even a strong classifier score cannot confirm a case or outbreak. No medication or dosage is produced.

The RandomForest learns from 4,000 synthetic rows. Its 1,200 held-out rows use a different fixed random seed and are checked for exact feature-vector overlap. Labels are chosen as synthetic latent categories before the symptom observations are sampled; production rules do not assign training labels. Symptom overlap, missing temperatures, conflicting observations, vaccination history and recent illness produce imperfect classification. Training and evaluation still share the same generator, so this is a reproducibility and engineering exercise, not evidence of field generalization.

Inputs are nine symptom flags, five species flags, temperature and missingness, age, appetite, milk change, activity, recent contact/movement, herd mortality, symptom duration, disease-specific vaccination gaps and recent dated EHR illness. The trained model, feature names, runtime version, seeds and parameters are stored together. No identifier, village name or owner identity is used to train it.

`ml/evaluation.json` contains the calculated accuracy, macro precision, macro recall, macro F1, per-class metrics, confusion matrix and sample hashes. These metrics apply to the standalone classifier. Live triage applies additional species/cardinal-symptom/uncertainty gates and has deterministic scenario tests separately. Model output is an **uncalibrated synthetic class score**, not the chance that a real animal has a disease.

Live rules only allow LSD for cattle/water buffalo with skin observations. A specific FMD suggestion requires mouth/foot lesions. Unsupported or overlapping patterns remain undifferentiated. A rules-only fallback handles missing or incompatible artifacts with `probability: null`; it retains urgent escalation for mortality, inability to stand and severe observations. A low score is not a veterinary clearance.

Run `.venv\Scripts\python.exe -m ml.train` from the repository root to reproduce the artifacts. Use the checked-in backend dependency lock to reproduce the scikit-learn runtime. Retrain after changing the feature schema or runtime; API startup never silently retrains. The local joblib file is trusted code-bearing build output; do not replace it with untrusted downloads or uploaded files.

Before any real-world use, obtain veterinarian-reviewed labelled data with consent, define clinically appropriate categories and species/age handling, establish external site/time validation, evaluate calibration and harms, and validate the complete workflow with domain professionals.
