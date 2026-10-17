"""A bounded priority index with exact, auditable factor contributions."""

from math import floor, isfinite

from app.triage.context import observation_time, recent_disease_history, vaccination_context

VERSION = 'risk-v1'
FACTOR_BUDGET = {'symptom_match': 28, 'disease_probability': 12, 'mortality': 15,
                 'vaccination': 12, 'vulnerability': 8, 'recent_contact': 5,
                 'nearby_activity': 12, 'cluster_strength': 8}


def risk_level(score, thresholds=(30, 60, 80)):
    if len(thresholds) != 3 or not (0 < thresholds[0] < thresholds[1] < thresholds[2] <= 100):
        raise ValueError('Risk thresholds must be three increasing numbers between 1 and 100.')
    return ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')[sum(score >= threshold for threshold in thresholds)]


def bounded(value, maximum=1.0):
    value = float(value or 0)
    if not isfinite(value):
        raise ValueError('Risk inputs must be finite.')
    return min(maximum, max(0.0, value))


def points(value):
    return int(floor(value + 0.5))


def calculate_risk(report, animal, triage, nearby_count=0, cluster_score=0, now=None):
    now = observation_time(now)
    vaccine = vaccination_context(report, animal, triage.get('disease_code', 'undifferentiated'), now)
    strength = bounded(triage.get('rule_strength', 0))
    # Mortality/recumbency are independently urgent even when no disease is recognizable.
    acute = []
    if report.get('activity') == 'recumbent':
        strength = max(strength, 0.85)
        acute.append('inability to stand: minimum evidence strength 0.85')
    if (report.get('temperature_c') or 0) >= 41:
        strength = max(strength, 0.85)
        acute.append('temperature at or above prototype 41 C severe-observation threshold: minimum 0.85')
    if report.get('appetite') == 'none':
        strength = max(strength, 0.5)
        acute.append('no appetite: minimum evidence strength 0.50')
    symptom_detail = f'Rule evidence strength {triage.get("rule_strength", 0):.2f}; '
    symptom_detail += ('; '.join(acute) + '; ') if acute else ''
    symptom_detail += f'effective evidence {strength:.2f} x 28; no language model calculation.'
    probability = triage.get('probability')
    known_disease = triage.get('disease_code') != 'undifferentiated'
    model_points = points(12 * bounded(probability)) if probability is not None and known_disease else 0
    age = animal.get('age_months', 36)
    recent_history = recent_disease_history(animal, now)
    age_points = 8 if age < 12 else (4 if age >= 120 else 0)
    vulnerability = min(8, age_points + (4 if recent_history else 0))
    age_detail = f"Animal age: {age} months; {'recent disease within 90 days' if recent_history else 'no recent dated disease history'}; contribution capped at 8."
    near = bounded(nearby_count, 1_000_000)
    cluster = bounded(cluster_score, 100)
    values = [
        ('symptom_match', 'Symptom pattern / acute observations', points(28 * strength), symptom_detail),
        ('disease_probability', 'Synthetic classifier support', model_points,
         f'Uncalibrated synthetic model score {probability:.4f} x 12; not a clinical likelihood.' if probability is not None and known_disease else 'No specific model probability contributes; unknown patterns and rules-only mode add zero.'),
        ('mortality', 'Reported mortality', 15 if report.get('mortality_count', 0) > 0 else 0,
         f"{report.get('mortality_count', 0)} reported herd deaths; any mortality adds 15 and independently triggers urgent review."),
        ('vaccination', 'Disease-specific vaccination gap', {'overdue': 12, 'unknown': 6}.get(vaccine['status'], 0), vaccine['detail']),
        ('vulnerability', 'Animal vulnerability / recent history', vulnerability, age_detail),
        ('recent_contact', 'Recent animal contact / movement', 5 if report.get('recent_contact') else 0,
         'Reported recent contact or movement.' if report.get('recent_contact') else 'No recent contact or movement reported.'),
        ('nearby_activity', 'Nearby similar animal episodes', min(12, points(near * 2)), f'{near:g} nearby similar distinct-animal episodes x 2; capped at 12.'),
        ('cluster_strength', 'Spatio-temporal cluster context', points(cluster * 0.08), f'Cluster score {cluster:g} / 100 x 8; zero when no cluster context has been calculated.'),
    ]
    factors = [{'key': key, 'label': label, 'points': value, 'detail': detail} for key, label, value, detail in values]
    score = sum(factor['points'] for factor in factors)
    return {'score': score, 'level': risk_level(score), 'factors': factors, 'version': VERSION}
