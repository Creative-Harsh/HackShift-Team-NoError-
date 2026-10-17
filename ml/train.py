"""From repository root: .venv/Scripts/python -m ml.train

Train once offline, write a trusted model artifact and measured held-out report.
No training runs on API startup, and no operational report is used as a label.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

import joblib
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support

from app.triage.features import FEATURE_NAMES, FEATURE_VERSION, feature_vector
from ml.synthetic import CLASSES, GENERATOR_VERSION, REFERENCE_TIME, generate_dataset

MODEL_VERSION = 'synthetic-rf-v1'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def train():
    train_rows = generate_dataset(per_class=800, seed=26128)
    test_rows = generate_dataset(per_class=240, seed=26129)
    x_train = [feature_vector(row['report'], row['animal'], REFERENCE_TIME) for row in train_rows]
    y_train = [row['label'] for row in train_rows]
    x_test = [feature_vector(row['report'], row['animal'], REFERENCE_TIME) for row in test_rows]
    y_test = [row['label'] for row in test_rows]
    overlap = len(set(map(tuple, x_train)) & set(map(tuple, x_test)))
    if overlap:
        raise RuntimeError(f'Unexpected training/test feature overlap: {overlap}')
    parameters = dict(n_estimators=180, max_depth=12, min_samples_leaf=4,
                      class_weight='balanced_subsample', random_state=26128, n_jobs=1)
    model = RandomForestClassifier(**parameters)
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, predicted, average='macro', zero_division=0)
    artifact_dir = ROOT / 'backend' / 'app' / 'triage' / 'artifacts'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / 'model.joblib'
    joblib.dump(model, model_path, compress=3)
    metadata = {
        'model_version': MODEL_VERSION, 'generator_version': GENERATOR_VERSION,
        'feature_version': FEATURE_VERSION, 'feature_names': list(FEATURE_NAMES),
        'classes': list(model.classes_), 'sklearn_version': sklearn.__version__,
        'training_rows': len(train_rows), 'training_seed': 26128, 'heldout_seed': 26129,
        'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
        'parameters': parameters, 'source': 'Entirely synthetic; no government or clinical patient data',
    }
    write_json(artifact_dir / 'metadata.json', metadata)
    evaluation = {
        'model_version': MODEL_VERSION, 'generator_version': GENERATOR_VERSION,
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'dataset_type': 'synthetic', 'clinical_validation': False,
        'evaluation_scope': 'RandomForest classifier on independently generated held-out synthetic rows; not complete triage pipeline or clinical performance.',
        'split': {'training_rows': len(train_rows), 'heldout_rows': len(test_rows),
                  'training_seed': 26128, 'heldout_seed': 26129, 'overlapping_feature_vectors': overlap,
                  'training_sha256': fingerprint(train_rows), 'heldout_sha256': fingerprint(test_rows)},
        'accuracy': float(accuracy_score(y_test, predicted)), 'precision_macro': float(precision),
        'recall_macro': float(recall), 'f1_macro': float(f1),
        'classes': list(CLASSES), 'confusion_matrix': confusion_matrix(y_test, predicted, labels=CLASSES).tolist(),
        'per_class': classification_report(y_test, predicted, labels=CLASSES, output_dict=True, zero_division=0),
        'limitations': ['Synthetic latent classes and observation frequencies are engineering assumptions.',
                       'A shared generator limits distribution-shift evidence despite separate random samples.',
                       'Model scores are uncalibrated; no sensitivity, specificity or accuracy claim on real livestock is supported.',
                       'Rules constrain live suggestions by species, cardinal symptoms and uncertainty; classifier metrics do not evaluate these postprocessing rules.'],
    }
    write_json(ROOT / 'ml' / 'evaluation.json', evaluation)
    print(json.dumps({key: evaluation[key] for key in ('accuracy', 'precision_macro', 'recall_macro', 'f1_macro')}, indent=2))
    print(f'Trained {len(train_rows)} synthetic rows; evaluated {len(test_rows)} held-out rows; feature overlap {overlap}.')
    return evaluation


if __name__ == '__main__':
    train()
