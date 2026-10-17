"""Measured toy surveillance scenarios, not prospective field validation.

Run from root: .venv/Scripts/python -m ml.evaluate_outbreak
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.geospatial import haversine_km
from app.outbreak import OutbreakConfig, detect_clusters

NOW = datetime(2026, 9, 12, 10, tzinfo=timezone.utc)
CENTER = [73.675, 18.722]


def observation(index, *, ago=6, lon=None, lat=None, disease='lsd', animal_id=None, **changes):
    return {'_id': f'scenario-case-{index:04}', 'animal_id': animal_id or f'scenario-animal-{index:04}',
            'triage': {'disease_code': disease},
            'report': {'symptoms': ['fever', 'skin_lesions', 'swelling'], 'temperature_c': 40,
                       'vaccination_status': 'overdue'},
            'effective_vaccination_status': 'overdue',
            'reported_at': NOW - timedelta(hours=ago), 'created_at': NOW,
            'location': {'type': 'Point', 'coordinates': [lon if lon is not None else CENTER[0] + index * .0001,
                                                        lat if lat is not None else CENTER[1]]},
            'district': 'Synthetic Pune', 'village': 'Synthetic Village A',
            'status': 'triage', 'confirmation_status': 'suspected', **changes}


def scenarios():
    cases = {
        'A_geographically_distant': [observation(index, lon=CENTER[0] + index * .2) for index in range(6)],
        'B_months_apart': [observation(index, ago=800 + index * 720) for index in range(6)],
        'C_similar_recent_cluster': [observation(index, ago=60 - index * 9) for index in range(6)],
        'D_rapid_concentration': [observation(index, ago=22 - index * 2) for index in range(11)],
        'duplicate_single_animal': [observation(index, animal_id='one-animal') for index in range(12)],
        'unrelated_categories': [observation(index, disease=('lsd', 'fmd', 'respiratory')[index % 3]) for index in range(6)],
        'future_observations': [observation(index, ago=-10) for index in range(6)],
        'symptom_disagreement': [observation(index, report={'symptoms': [('fever', 'skin_lesions', 'swelling')[index % 3]],
                                                         'vaccination_status': 'overdue'}) for index in range(6)],
    }
    return cases


def evaluate():
    baseline = [observation(999, ago=240)]
    # Place the synthetic historical incident inside the demonstrated village.
    baseline[0]['location']['coordinates'] = CENTER[:]
    negative = ('A_geographically_distant', 'B_months_apart', 'duplicate_single_animal',
                'unrelated_categories', 'future_observations', 'symptom_disagreement')
    positive = ('C_similar_recent_cluster', 'D_rapid_concentration')
    behavior = {}
    for name, cases in scenarios().items():
        started = perf_counter()
        groups = detect_clusters(cases, baseline, NOW, OutbreakConfig())
        runtime_ms = (perf_counter() - started) * 1000
        behavior[name] = {'input_reports': len(cases), 'flagged_groups': len(groups),
                          'scores': [group['score'] for group in groups],
                          'states': [group['status'] for group in groups],
                          'intensity': [group['level'] for group in groups],
                          'calculation_ms': round(runtime_ms, 3)}
        if name in positive and groups:
            behavior[name]['localization_error_km'] = min(haversine_km(CENTER, group['center']['coordinates']) for group in groups)
    replay = [observation(index, ago=hours) for index, hours in enumerate((48, 42, 36, 30, 24, 18, 12, 10, 8, 4, 0))]
    first_flag = first_suspected = None
    trace = []
    for count in range(1, len(replay) + 1):
        timestamp = replay[count - 1]['reported_at']
        groups = detect_clusters(replay[:count], baseline, timestamp, OutbreakConfig())
        if groups and first_flag is None:
            first_flag = timestamp
        if any(group['status'] == 'suspected_outbreak' for group in groups) and first_suspected is None:
            first_suspected = timestamp
        trace.append({'reports_received': count, 'observation_time': timestamp.isoformat(),
                      'scores': [group['score'] for group in groups], 'states': [group['status'] for group in groups]})
    count_only = replay[5]['reported_at']
    false_alerts = sum(behavior[name]['flagged_groups'] > 0 for name in negative)
    missed = sum(behavior[name]['flagged_groups'] == 0 for name in positive)
    # Show historical incidence changes the same current observations' score.
    dense_baseline = [observation(1000 + index, ago=100 + index * 3, lon=CENTER[0]) for index in range(150)]
    sparse_score = detect_clusters(scenarios()['C_similar_recent_cluster'], baseline, NOW)[0]['score']
    dense_groups = detect_clusters(scenarios()['C_similar_recent_cluster'], dense_baseline, NOW)
    evaluation = {
        'engine_version': 'outbreak-v1', 'dataset_type': 'constructed_synthetic_scenarios', 'field_validation': False,
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'scenario_behavior': behavior,
        'false_alerts': {'count': false_alerts, 'negative_scenarios': len(negative), 'rate': false_alerts / len(negative)},
        'missed_clusters': {'count': missed, 'positive_scenarios': len(positive), 'rate': missed / len(positive)},
        'lead_time': {
            'reference': 'Toy comparator: first sixth distinct similar local animal report in this exact synthetic replay. Not a field-surveillance benchmark.',
            'count_only_reference_at': count_only.isoformat(),
            'first_abnormal_alert_at': first_flag.isoformat() if first_flag else None,
            'first_suspected_at': first_suspected.isoformat() if first_suspected else None,
            'abnormal_alert_lead_hours': (count_only - first_flag).total_seconds() / 3600 if first_flag else None,
            'suspected_alert_lead_hours': (count_only - first_suspected).total_seconds() / 3600 if first_suspected else None,
            'first_report_to_alert_hours': (first_flag - replay[0]['reported_at']).total_seconds() / 3600 if first_flag else None,
        },
        'baseline_sensitivity': {'same_active_reports': 6, 'sparse_baseline_score': sparse_score,
                                 'dense_baseline_score': dense_groups[0]['score'] if dense_groups else None,
                                 'dense_baseline_flagged': bool(dense_groups)},
        'replay_trace': trace,
        'limitations': ['Six designed negative and two positive scenarios cannot estimate a real-world false-alert or missed-outbreak rate.',
                       'All thresholds, disease labels and historical baselines are prototype simulation inputs.',
                       'Lead time compares two rules on the same known synthetic replay, not disease onset, veterinary detection or prospective surveillance.',
                       'Calculation timings measure only this local pure engine call, not network, queue, dispatch or field response latency.'],
    }
    destination = ROOT / 'ml' / 'outbreak_evaluation.json'
    destination.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({key: evaluation[key] for key in ('false_alerts', 'missed_clusters', 'lead_time', 'baseline_sensitivity')}, indent=2))
    return evaluation


if __name__ == '__main__':
    evaluate()
