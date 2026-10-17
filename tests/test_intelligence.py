"""Deterministic clinical-safety boundaries and exact factor accounting."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.risk_engine import FACTOR_BUDGET, calculate_risk, risk_level
from app.triage import assess, classifier
from app.triage.context import vaccination_context
from app.triage.features import FEATURE_NAMES, feature_vector
from ml.synthetic import generate_dataset

NOW = datetime(2026, 9, 11, 10, tzinfo=timezone.utc)


def bovine(**changes):
    return {'species': 'cattle', 'age_months': 9, 'vaccination_history': [
        {'vaccine': 'LSD', 'date_given': '2025-07-01', 'next_due_date': '2026-07-01'}],
        'disease_history': [], **changes}


def observations(**changes):
    return {'symptoms': ['fever', 'skin_lesions', 'swelling'], 'temperature_c': 40.0,
            'appetite': 'reduced', 'milk_drop_percent': 25, 'activity': 'reduced',
            'recent_contact': True, 'vaccination_status': 'overdue', 'mortality_count': 0,
            'duration_hours': 24, **changes}


def factor(result, key):
    return next(row for row in result['factors'] if row['key'] == key)


def test_model_artifact_is_loaded_with_synthetic_provenance():
    result = assess(observations(), bovine(), NOW)
    assert result['model_version'] == 'synthetic-rf-v1'
    assert result['probability_kind'] == 'uncalibrated_synthetic_model_score'
    assert 0 < result['probability'] < 1
    assert 'Synthetic' in result['model_source']
    assert result['suspected_disease'] == 'Possible Lumpy Skin Disease'
    assert 'confirmed' not in result['suspected_disease'].lower()


def test_canonical_demo_is_high_with_transparent_score():
    report, animal = observations(), bovine()
    triage = assess(report, animal, NOW)
    risk = calculate_risk(report, animal, triage, now=NOW)
    assert risk['level'] == 'HIGH'
    assert risk['score'] == sum(row['points'] for row in risk['factors'])
    assert factor(risk, 'symptom_match')['points'] == 28
    assert factor(risk, 'vaccination')['points'] == 12
    assert factor(risk, 'vulnerability')['points'] == 8
    assert factor(risk, 'nearby_activity')['points'] == 0


@pytest.mark.parametrize('species', ['goat', 'sheep', 'pig'])
def test_species_cannot_receive_lsd_suggestion(species):
    result = assess(observations(), bovine(species=species), NOW)
    assert result['disease_code'] == 'undifferentiated'
    assert any('SPECIES_EXCLUDED' in item for item in result['triggered_rules'])


@pytest.mark.parametrize('species', ['cattle', 'buffalo', 'goat', 'sheep', 'pig'])
def test_fmd_cardinal_pattern_across_supported_species(species):
    result = assess(observations(symptoms=['mouth_foot_lesions', 'drooling', 'fever']), bovine(species=species), NOW)
    assert result['disease_code'] == 'fmd'
    assert result['severity'] == 'high'
    assert any('laboratory' in item.lower() for item in result['missing_information'])


def test_unsupported_empty_pattern_remains_unknown_even_if_model_is_confident(monkeypatch):
    monkeypatch.setattr(classifier, 'predict', lambda *args: ({'lsd': .99, 'undifferentiated': .01}, 'test-model'))
    result = assess(observations(symptoms=[], temperature_c=None), bovine(), NOW)
    assert result['disease_code'] == 'undifferentiated'
    assert 'Measured temperature' in result['missing_information']


def test_overlapping_cardinal_patterns_remain_uncertain():
    result = assess(observations(symptoms=['fever', 'skin_lesions', 'swelling', 'mouth_foot_lesions', 'drooling']), bovine(), NOW)
    assert result['disease_code'] == 'undifferentiated'
    assert any('CONFLICTING_PATTERNS' in rule for rule in result['triggered_rules'])
    assert result['severity'] == 'high'


def test_rules_only_fallback_is_explicit_and_preserves_urgent_triage(monkeypatch):
    monkeypatch.setattr(classifier, 'load_model', lambda: (None, None))
    report = observations(mortality_count=1)
    result = assess(report, bovine(), NOW)
    risk = calculate_risk(report, bovine(), result, now=NOW)
    assert result['disease_code'] == 'lsd'
    assert result['probability'] is None
    assert result['probability_kind'] == 'unavailable_rules_only'
    assert result['severity'] == 'critical'
    assert 'immediately' in result['recommended_escalation']
    assert factor(risk, 'disease_probability')['points'] == 0


def test_mortality_alone_requires_professional_review_despite_low_pattern_score():
    report = observations(symptoms=[], temperature_c=None, mortality_count=1,
                          appetite='normal', activity='normal', recent_contact=False)
    result = assess(report, bovine(age_months=36), NOW)
    assert result['severity'] == 'critical'
    assert result['disease_code'] == 'undifferentiated'
    assert any('MORTALITY_ALERT' in row for row in result['triggered_rules'])


@pytest.mark.parametrize(('temperature', 'appetite', 'expected'), [(41.2, 'normal', 24), (38.5, 'none', 14)])
def test_severe_measurements_contribute_even_without_specific_pattern(temperature, appetite, expected):
    report = observations(symptoms=[], temperature_c=temperature, appetite=appetite)
    result = assess(report, bovine(), NOW)
    risk = calculate_risk(report, bovine(), result, now=NOW)
    assert result['severity'] == 'high'
    assert factor(risk, 'symptom_match')['points'] == expected
    assert 'minimum' in factor(risk, 'symptom_match')['detail']


def test_latest_relevant_vaccination_wins_and_other_vaccines_do_not_cancel_gap():
    animal = bovine(vaccination_history=[
        {'vaccine': 'LSD', 'date_given': '2025-01-01', 'next_due_date': '2026-01-01'},
        {'vaccine': 'LSD', 'date_given': '2026-08-01', 'next_due_date': '2027-08-01'},
    ])
    report = observations(vaccination_status='unknown')
    assert vaccination_context(report, animal, 'lsd', NOW)['status'] == 'up_to_date'
    assert vaccination_context(report, animal, 'fmd', NOW)['status'] == 'unknown'
    # A vaccine entered after the observation must not influence that old report.
    historical = NOW - timedelta(days=50)
    assert vaccination_context(report, animal, 'lsd', historical)['status'] == 'overdue'


def test_self_report_conflict_explained_without_cancelling_overdue_record():
    context = vaccination_context(observations(vaccination_status='up_to_date'), bovine(), 'lsd', NOW)
    assert context['status'] == 'overdue'
    assert 'discrepancy' in context['detail']


def test_invalid_future_vaccination_ignored_and_history_is_order_independent():
    animal = bovine(vaccination_history=[
        {'vaccine': 'LSD', 'date_given': '2027-01-01', 'next_due_date': '2028-01-01'},
        {'vaccine': 'LSD', 'date_given': '2026-01-01', 'next_due_date': '2025-01-01'},
    ])
    assert vaccination_context(observations(vaccination_status='unknown'), animal, 'lsd', NOW)['status'] == 'unknown'


def test_recent_disease_context_increases_vulnerability_but_old_history_does_not():
    report = observations()
    triage = assess(report, bovine(), NOW)
    recent = bovine(age_months=36, disease_history=[{'diagnosis': 'Prior illness', 'date': '2026-09-01'}])
    old = bovine(age_months=36, disease_history=[{'diagnosis': 'Prior illness', 'date': '2024-09-01'}])
    assert factor(calculate_risk(report, recent, triage, now=NOW), 'vulnerability')['points'] == 4
    assert factor(calculate_risk(report, old, triage, now=NOW), 'vulnerability')['points'] == 0


@pytest.mark.parametrize(('score', 'level'), [(0, 'LOW'), (29, 'LOW'), (30, 'MODERATE'),
                                         (59, 'MODERATE'), (60, 'HIGH'), (79, 'HIGH'),
                                         (80, 'CRITICAL'), (100, 'CRITICAL')])
def test_risk_band_boundaries(score, level):
    assert risk_level(score) == level


def test_maximum_risk_has_exact_factor_budget():
    triage = {'disease_code': 'lsd', 'rule_strength': 1, 'probability': 1}
    result = calculate_risk(observations(mortality_count=4), bovine(), triage, nearby_count=100, cluster_score=1000, now=NOW)
    assert result['score'] == 100
    assert result['level'] == 'CRITICAL'
    assert {row['key']: row['points'] for row in result['factors']} == FACTOR_BUDGET
    assert all(row['detail'] for row in result['factors'])


def test_risk_context_is_monotonic_and_capped():
    report, animal = observations(), bovine()
    triage = assess(report, animal, NOW)
    scores = [calculate_risk(report, animal, triage, nearby_count=n, cluster_score=n * 10, now=NOW)['score'] for n in range(20)]
    assert scores == sorted(scores)
    assert scores[-1] <= 100


def test_unknown_class_probability_does_not_raise_disease_risk():
    triage = {'disease_code': 'undifferentiated', 'rule_strength': 0, 'probability': 1}
    result = calculate_risk(observations(), bovine(), triage, now=NOW)
    assert factor(result, 'disease_probability')['points'] == 0
    assert factor(result, 'vaccination')['points'] == 0


def test_assess_and_risk_are_deterministic_without_mutating_reports():
    report, animal = observations(), bovine()
    before = deepcopy((report, animal))
    result = assess(report, animal, NOW)
    assert result == assess(report, animal, NOW)
    assert calculate_risk(report, animal, result, now=NOW) == calculate_risk(report, animal, result, now=NOW)
    assert (report, animal) == before
    assert len(feature_vector(report, animal, NOW)) == len(FEATURE_NAMES)


def test_synthetic_generator_reproducible_and_explicit():
    rows = generate_dataset(per_class=8, seed=123)
    assert rows == generate_dataset(per_class=8, seed=123)
    assert len(rows) == 40
    assert all(row['is_synthetic'] for row in rows)
    assert all(row['animal']['species'] in ('cattle', 'buffalo') for row in rows if row['label'] == 'lsd')


def test_nonfinite_risk_inputs_rejected():
    with pytest.raises(ValueError):
        calculate_risk(observations(), bovine(), {'rule_strength': float('nan')}, now=NOW)


def test_naive_assessment_time_rejected():
    with pytest.raises(ValueError):
        assess(observations(), bovine(), datetime(2026, 9, 11))
