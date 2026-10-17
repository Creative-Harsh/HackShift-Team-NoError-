"""Deterministic spatio-temporal safeguards with actual engine calculations."""

from copy import deepcopy
from datetime import timedelta
from random import Random

import pytest

from app.geospatial import haversine_km
from app.outbreak import OutbreakConfig, case_similarity, detect_clusters
from app.outbreak.engine import FACTOR_BUDGET
from ml.evaluate_outbreak import CENTER, NOW, observation, scenarios


@pytest.mark.parametrize('name', ['A_geographically_distant', 'B_months_apart', 'duplicate_single_animal',
                                 'unrelated_categories', 'future_observations', 'symptom_disagreement'])
def test_negative_scenarios_do_not_form_clusters(name):
    assert detect_clusters(scenarios()[name], [], NOW) == []


def test_similar_recent_reports_form_a_scored_cluster():
    result = detect_clusters(scenarios()['C_similar_recent_cluster'], [], NOW)
    assert len(result) == 1
    assert result[0]['animal_count'] == 6
    assert result[0]['status'] == 'suspected_outbreak'
    assert result[0]['score'] == sum(factor['points'] for factor in result[0]['factors'])
    assert all(factor['detail'] for factor in result[0]['factors'])
    assert {factor['key'] for factor in result[0]['factors']} == set(FACTOR_BUDGET)


def test_rapid_concentration_is_critical_without_official_confirmation():
    result = detect_clusters(scenarios()['D_rapid_concentration'], [], NOW)[0]
    assert result['score'] >= 80
    assert result['level'] == 'CRITICAL'
    assert result['status'] == 'suspected_outbreak'
    assert all(factor['points'] <= FACTOR_BUDGET[factor['key']] for factor in result['factors'])


def test_first_report_is_isolated_and_evidence_guard_prevents_four_case_outbreak():
    reports = [observation(index) for index in range(5)]
    assert detect_clusters(reports[:1], [], NOW) == []
    assert detect_clusters(reports[:2], [], NOW) == []
    assert detect_clusters(reports[:3], [], NOW)[0]['status'] == 'abnormal_cluster'
    assert detect_clusters(reports[:4], [], NOW)[0]['status'] == 'abnormal_cluster'
    assert detect_clusters(reports, [], NOW)[0]['status'] == 'suspected_outbreak'


def test_local_historical_baseline_reduces_alert_strength():
    reports = scenarios()['C_similar_recent_cluster']
    dense = [observation(100 + index, ago=100 + index * 3, lon=CENTER[0]) for index in range(150)]
    first = detect_clusters(reports, [], NOW)[0]
    second = detect_clusters(reports, dense, NOW)[0]
    assert second['score'] < first['score']
    assert next(factor for factor in second['factors'] if factor['key'] == 'historical_excess')['points'] == 0
    remote = deepcopy(dense)
    for case in remote:
        case['location']['coordinates'][0] += 1
    assert detect_clusters(reports, remote, NOW)[0]['score'] == first['score']


def test_baseline_cannot_include_active_or_future_incidents():
    reports = scenarios()['D_rapid_concentration']
    invalid_baseline = reports + [observation(100 + index, ago=-20) for index in range(150)]
    assert detect_clusters(reports, invalid_baseline, NOW) == detect_clusters(reports, [], NOW)


def test_latest_rejected_or_unknown_report_supersedes_older_same_animal_signal():
    cases = [observation(index, ago=12) for index in range(3)]
    assert detect_clusters(cases, [], NOW)
    newer = observation(99, animal_id=cases[0]['animal_id'], ago=1, status='rejected')
    assert detect_clusters(cases + [newer], [], NOW) == []
    newer['status'] = 'triage'
    newer['triage']['disease_code'] = 'undifferentiated'
    assert detect_clusters(cases + [newer], [], NOW) == []


def test_duplicate_reports_do_not_increase_existing_group_score_or_animal_count():
    reports = [observation(index) for index in range(6)]
    before = detect_clusters(reports, [], NOW)[0]
    duplicates = deepcopy(reports)
    for case in duplicates:
        case['_id'] += '-older'
        case['reported_at'] -= timedelta(hours=1)
    after = detect_clusters(reports + duplicates, [], NOW)[0]
    assert after == before


def test_closed_recent_cases_remain_incident_evidence_until_age_out():
    reports = [observation(index, status='closed', confirmation_status='confirmed') for index in range(6)]
    assert detect_clusters(reports, [], NOW)
    assert detect_clusters(reports, [], NOW + timedelta(hours=80)) == []


def test_receipt_time_does_not_make_old_offline_reports_an_active_cluster():
    reports = [observation(index, ago=100) for index in range(8)]
    assert all(case['created_at'] == NOW for case in reports)
    assert detect_clusters(reports, [], NOW) == []


def test_permutation_invariant_without_mutating_case_inputs():
    reports = scenarios()['D_rapid_concentration']
    original = deepcopy(reports)
    expected = detect_clusters(reports, [], NOW)
    for seed in range(10):
        permutation = reports[:]
        Random(seed).shuffle(permutation)
        assert detect_clusters(permutation, [], NOW) == expected
    assert reports == original


def test_spatial_chains_cannot_bridge_unbounded_distances():
    reports = [observation(index, lon=CENTER[0] + index * .04) for index in range(15)]
    lookup = {case['_id']: case for case in reports}
    groups = detect_clusters(reports, [], NOW)
    assert len(groups) > 1
    used = []
    for group in groups:
        assert group['radius_km'] <= 5
        members = [lookup[identity] for identity in group['case_ids']]
        for left in members:
            assert haversine_km(left['location']['coordinates'], group['center']['coordinates']) <= 5 + 1e-9
            for right in members:
                assert haversine_km(left['location']['coordinates'], right['location']['coordinates']) <= 10 + 1e-9
        used.extend(group['case_ids'])
    assert len(used) == len(set(used))


def test_district_boundaries_and_species_category_similarity():
    reports = [observation(index, district='A' if index < 3 else 'B') for index in range(6)]
    groups = detect_clusters(reports, [], NOW)
    assert {group['district'] for group in groups} == {'A', 'B'}
    assert case_similarity(reports[0], reports[1]) == 1
    assert case_similarity(reports[0], observation(99, disease='fmd')) == 0


def test_dateline_center_stays_near_actual_cases():
    reports = [observation(index, lon=longitude, lat=0) for index, longitude in enumerate((179.99, -179.995, 179.999))]
    group = detect_clusters(reports, [], NOW)[0]
    assert abs(group['center']['coordinates'][0]) > 179.9
    assert group['radius_km'] < 2


def test_changing_case_risk_cannot_circularly_amplify_cluster_score():
    reports = scenarios()['D_rapid_concentration']
    original = detect_clusters(reports, [], NOW)
    for report in reports:
        report['risk'] = {'score': 100, 'level': 'CRITICAL'}
    assert detect_clusters(reports, [], NOW) == original


def test_vaccination_context_changes_only_its_declared_factor():
    reports = scenarios()['D_rapid_concentration']
    original = detect_clusters(reports, [], NOW)[0]
    for report in reports:
        report['effective_vaccination_status'] = 'up_to_date'
    current = detect_clusters(reports, [], NOW)[0]
    assert original['score'] - current['score'] == 5
    assert [factor for factor in original['factors'] if factor['key'] != 'vaccination_gap'] == [factor for factor in current['factors'] if factor['key'] != 'vaccination_gap']


def test_maximum_analysis_limit_is_explicit_instead_of_silently_truncating():
    with pytest.raises(ValueError, match='exceeds'):
        detect_clusters([observation(index) for index in range(6)], [], NOW, OutbreakConfig(max_cases=5))


@pytest.mark.parametrize('options', [{'radius_km': 0}, {'baseline_days': float('nan')}, {'window_hours': 24},
                                    {'similarity_threshold': .5}, {'abnormal_threshold': 80}, {'min_cluster_animals': 2}])
def test_invalid_configuration_rejected(options):
    with pytest.raises(ValueError):
        OutbreakConfig(**options)
