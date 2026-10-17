"""Load only the locally built, trusted prototype artifact; never download models."""

import hashlib
import json
import logging
import pickle
import struct
from functools import lru_cache
from pathlib import Path

from .features import FEATURE_NAMES, FEATURE_VERSION, feature_vector

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path(__file__).resolve().parent / 'artifacts'
MODEL_SOURCE = 'Synthetic prototype training data; not clinical validation'


@lru_cache(maxsize=1)
def load_model():
    try:
        import joblib
        import sklearn

        metadata = json.loads((ARTIFACT_DIR / 'metadata.json').read_text(encoding='utf-8'))
        if not isinstance(metadata.get('model_version'), str) or not metadata['model_version']:
            raise ValueError('Model version metadata missing')
        if metadata['feature_version'] != FEATURE_VERSION or metadata['feature_names'] != list(FEATURE_NAMES):
            raise ValueError('Model feature schema mismatch')
        if metadata['sklearn_version'] != sklearn.__version__:
            raise ValueError('Model runtime version mismatch; retrain with the installed scikit-learn')
        model_path = ARTIFACT_DIR / 'model.joblib'
        if hashlib.sha256(model_path.read_bytes()).hexdigest() != metadata['model_sha256']:
            raise ValueError('Model artifact checksum mismatch')
        # joblib deserializes Python objects. Only this repository's trusted artifact is allowed.
        model = joblib.load(model_path)
        return model, metadata
    except (OSError, ValueError, KeyError, ImportError, EOFError, TypeError,
            pickle.UnpicklingError, struct.error, IndexError, AttributeError) as exc:
        logger.warning('Prototype classifier unavailable; using deterministic rules: %s', exc)
        return None, None


def predict(report, animal, now):
    model, metadata = load_model()
    if model is None:
        return None, 'rules-v1'
    try:
        values = model.predict_proba([feature_vector(report, animal, now)])[0]
        return {str(label): float(value) for label, value in zip(model.classes_, values)}, metadata['model_version']
    except (ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        logger.warning('Prototype inference failed; using rules: %s', exc)
        return None, 'rules-v1'
