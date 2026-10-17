"""One versioned feature transform shared by training and live inference."""

from .context import recent_disease_history, vaccination_context

FEATURE_VERSION = 'structured-v1'
SYMPTOM_KEYS = ('fever', 'cough', 'nasal_discharge', 'drooling', 'skin_lesions',
                'mouth_foot_lesions', 'diarrhea', 'weakness', 'swelling')
SPECIES = ('cattle', 'buffalo', 'goat', 'sheep', 'pig')
FEATURE_NAMES = (
    *SYMPTOM_KEYS, *(f'species_{species}' for species in SPECIES),
    'temperature_c', 'temperature_missing', 'age_months', 'appetite_reduced', 'appetite_none',
    'milk_drop_percent', 'activity_reduced', 'activity_recumbent', 'recent_contact',
    'mortality_present', 'duration_hours', 'lsd_vaccine_gap', 'fmd_vaccine_gap', 'recent_disease',
)


def symptom_set(report):
    symptoms = set(report.get('symptoms', []))
    # 39.5 is a deliberately broad prototype signal, not a species diagnostic cutoff.
    if report.get('temperature_c') is not None and report['temperature_c'] >= 39.5:
        symptoms.add('fever')
    return symptoms


def feature_vector(report, animal, now):
    symptoms = symptom_set(report)
    temperature = report.get('temperature_c')
    gaps = {'overdue': 1.0, 'unknown': 0.5, 'up_to_date': 0.0, 'not_applicable': 0.0}
    return [
        *(float(name in symptoms) for name in SYMPTOM_KEYS),
        *(float(animal.get('species') == species) for species in SPECIES),
        float(temperature if temperature is not None else 38.5), float(temperature is None),
        float(animal.get('age_months', 36)), float(report.get('appetite') == 'reduced'),
        float(report.get('appetite') == 'none'), float(report.get('milk_drop_percent', 0)),
        float(report.get('activity') == 'reduced'), float(report.get('activity') == 'recumbent'),
        float(bool(report.get('recent_contact'))), float(report.get('mortality_count', 0) > 0),
        float(report.get('duration_hours', 0)),
        gaps[vaccination_context(report, animal, 'lsd', now)['status']],
        gaps[vaccination_context(report, animal, 'fmd', now)['status']],
        float(recent_disease_history(animal, now)),
    ]
