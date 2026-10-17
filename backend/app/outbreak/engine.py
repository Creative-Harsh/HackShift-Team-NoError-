"""Bounded spatial neighborhoods, incident time, distinct animals and local baseline.

No database writes, model calls, risk-score inputs or official confirmation.
"""

from array import array
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, floor, isfinite, radians, sin, sqrt

from app.geospatial import haversine_km
from app.triage.features import SYMPTOM_KEYS, symptom_set
from app.triage.rules import DISEASE_LABELS

VERSION = 'outbreak-v1'
FACTOR_BUDGET = {'animal_burden': 20, 'spatial_concentration': 15, 'temporal_concentration': 15,
                 'similarity': 15, 'recent_growth': 15, 'historical_excess': 15, 'vaccination_gap': 5}


@dataclass(frozen=True)
class OutbreakConfig:
    radius_km: float = 5.0
    window_hours: float = 72.0
    baseline_days: float = 28.0
    growth_hours: float = 24.0
    similarity_threshold: float = 0.75
    abnormal_threshold: int = 40
    suspected_threshold: int = 65
    critical_threshold: int = 80
    min_cluster_animals: int = 3
    min_outbreak_animals: int = 5
    animal_saturation: int = 10
    max_cases: int = 2000

    def __post_init__(self):
        if not all(isfinite(value) and value > 0 for value in (self.radius_km, self.window_hours, self.baseline_days, self.growth_hours)):
            raise ValueError('Outbreak distances and time intervals must be positive and finite.')
        if self.window_hours < 2 * self.growth_hours:
            raise ValueError('Active window must contain both growth comparison intervals.')
        if not 0.65 < self.similarity_threshold <= 1:
            raise ValueError('Similarity threshold must require symptom agreement in addition to disease.')
        if not 0 < self.abnormal_threshold < self.suspected_threshold <= self.critical_threshold <= 100:
            raise ValueError('Outbreak thresholds must be increasing and bounded by 100.')
        if not 3 <= self.min_cluster_animals <= self.min_outbreak_animals <= self.animal_saturation:
            raise ValueError('Cluster evidence guards must be at least three distinct animals.')
        if not self.min_outbreak_animals <= self.max_cases <= 10_000:
            raise ValueError('Active-case limit must accommodate evidence guards and remain bounded.')


def _code(case):
    return str((case.get('triage') or {}).get('disease_code') or case.get('disease_code') or '')


def _mask(case):
    signs = symptom_set(case.get('report') or {})
    return sum(1 << index for index, name in enumerate(SYMPTOM_KEYS) if name in signs)


def _agreement(a, b):
    union = a | b
    return 0.65 + 0.35 * ((a & b).bit_count() / union.bit_count() if union else 0.0)


def case_similarity(a, b):
    """Same known category plus symptom Jaccard; incompatible categories score zero."""
    disease = _code(a)
    if disease not in DISEASE_LABELS or disease == 'undifferentiated' or disease != _code(b):
        return 0.0
    return _agreement(_mask(a), _mask(b))


def _time(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _normalize(case):
    observed = _time(case.get('reported_at'))
    coordinates = (case.get('location') or {}).get('coordinates')
    identity = case.get('_id') or case.get('id')
    if not observed or not identity or not case.get('animal_id'):
        return None
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
        return None
    try:
        lon, lat = map(float, coordinates)
    except (ValueError, TypeError):
        return None
    if not isfinite(lon) or not isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return {**case, '_engine_id': str(identity), '_observed': observed,
            '_coordinates': [lon, lat], '_disease': _code(case), '_mask': _mask(case)}


def _eligible(case):
    return (case['_disease'] in DISEASE_LABELS and case['_disease'] != 'undifferentiated'
            and case.get('status') != 'rejected' and case.get('confirmation_status') != 'rejected'
            and case['_mask'] != 0)


def _latest_animals(cases, start, end, include_end=True):
    latest = {}
    for raw in cases:
        case = _normalize(raw)
        if case is None or not (start <= case['_observed'] <= end if include_end else start <= case['_observed'] < end):
            continue
        animal_id = str(case['animal_id'])
        previous = latest.get(animal_id)
        if previous is None or (case['_observed'], case['_engine_id']) > (previous['_observed'], previous['_engine_id']):
            latest[animal_id] = case
    # Latest rejected/unknown observations suppress older same-animal signal.
    return sorted((case for case in latest.values() if _eligible(case)), key=lambda case: case['_engine_id'])


def incident_observations(cases, start, end):
    """Latest eligible observation per animal, shared by cluster and nearby-risk projections."""
    return _latest_animals(cases, start, end)


def _center(cases):
    x = y = z = 0.0
    for case in cases:
        lon, lat = map(radians, case['_coordinates'])
        x += cos(lat) * cos(lon)
        y += cos(lat) * sin(lon)
        z += sin(lat)
    return [degrees(atan2(y, x)), degrees(atan2(z, sqrt(x * x + y * y)))]


def _points(value):
    return int(floor(max(0.0, value) + 0.5))


def _vaccination_gap(case):
    if case['_disease'] not in ('lsd', 'fmd'):
        return 0.0
    status = case.get('effective_vaccination_status') or (case.get('report') or {}).get('vaccination_status', 'unknown')
    return {'overdue': 1.0, 'unknown': 0.5}.get(status, 0.0)


def _score(members, baseline, now, config):
    count = len(members)
    center = _center(members)
    distance_sum = similarity_sum = 0.0
    pair_count = count * (count - 1) // 2
    for index, left in enumerate(members):
        for right in members[index + 1:]:
            distance_sum += haversine_km(left['_coordinates'], right['_coordinates'])
            similarity_sum += _agreement(left['_mask'], right['_mask'])
    mean_distance = distance_sum / pair_count
    agreement = similarity_sum / pair_count
    first, last = min(case['_observed'] for case in members), max(case['_observed'] for case in members)
    span_hours = (last - first).total_seconds() / 3600
    recent_start, prior_start = now - timedelta(hours=config.growth_hours), now - timedelta(hours=2 * config.growth_hours)
    recent = sum(case['_observed'] >= recent_start for case in members)
    prior = sum(prior_start <= case['_observed'] < recent_start for case in members)
    ratio = (recent + 1) / (prior + 1)
    growth_evidence = min(1.0, count / 6.0)
    growth = min(1.0, max(0.0, (ratio - 1) / 3)) * growth_evidence
    local_baseline = [case for case in baseline if case['_disease'] == members[0]['_disease']
                      and case.get('district', '') == members[0].get('district', '')
                      and haversine_km(center, case['_coordinates']) <= config.radius_km]
    expected = max(1.0, len(local_baseline) * config.window_hours / (config.baseline_days * 24))
    excess = max(0.0, 1.0 - expected / count)
    vaccine_gap = sum(_vaccination_gap(case) for case in members) / count
    values = [
        ('animal_burden', 'Distinct affected animals', _points(20 * min(1.0, count / config.animal_saturation)),
         f'{count} distinct animals / saturation {config.animal_saturation} x 20; repeated reports count once.'),
        ('spatial_concentration', 'Spatial concentration', _points(15 * max(0.0, 1.0 - mean_distance / config.radius_km)),
         f'Mean pair distance {mean_distance:.3f} km / radius {config.radius_km:g} km; 15 x (1 - ratio), floored at zero.'),
        ('temporal_concentration', 'Observation-time concentration', _points(15 * max(0.0, 1.0 - span_hours / config.window_hours)),
         f'Observation span {span_hours:.2f} hours / active window {config.window_hours:g} hours; receipt time is not used.'),
        ('similarity', 'Disease and symptom agreement', _points(15 * agreement),
         f'Mean pair agreement {agreement:.3f}; 0.65 same category + 0.35 symptom Jaccard; x 15.'),
        ('recent_growth', 'Recent incident growth', _points(15 * growth),
         f'Last {config.growth_hours:g}h: {recent}; preceding {config.growth_hours:g}h: {prior}; smoothed ratio ({recent}+1)/({prior}+1)={ratio:.2f}; positive excess / 3, capped at 1, evidence weight {growth_evidence:.2f}.'),
        ('historical_excess', 'Excess above local historical incidence', _points(15 * excess),
         f'{len(local_baseline)} distinct local baseline animals in preceding {config.baseline_days:g} days; expected active-window count {expected:.2f} (floor 1); 15 x max(0, 1 - expected/{count}).'),
        ('vaccination_gap', 'Relevant vaccination gaps', _points(5 * vaccine_gap),
         f'Mean gap weight {vaccine_gap:.2f} x 5; overdue 1, unknown 0.5, current 0; disease-specific context only.'),
    ]
    factors = [{'key': key, 'label': label, 'points': value, 'detail': detail} for key, label, value, detail in values]
    score = sum(factor['points'] for factor in factors)
    status = 'suspected_outbreak' if score >= config.suspected_threshold and count >= config.min_outbreak_animals else 'abnormal_cluster'
    return {'case_ids': sorted(case['_engine_id'] for case in members), 'animal_count': count, 'case_count': count,
            'disease_code': members[0]['_disease'], 'suspected_disease': DISEASE_LABELS[members[0]['_disease']],
            'center': {'type': 'Point', 'coordinates': center},
            'radius_km': round(max(haversine_km(center, case['_coordinates']) for case in members), 4),
            'start_time': first, 'end_time': last, 'score': score,
            'level': 'CRITICAL' if score >= config.critical_threshold else ('HIGH' if score >= config.suspected_threshold else 'MODERATE'),
            'status': status, 'factors': factors, 'district': members[0].get('district', ''),
            'villages': sorted({case.get('village', '') for case in members}), 'version': VERSION}


def _partition_groups(cases, baseline, now, config):
    """A deterministic dense-seed partition, bounded even for geographic chains.

    The n*n float table needs ~16 MB for the hard limit of 2,000 animals; nearby
    neighbor lists avoid re-running all geometry for each possible seed.
    """
    size = len(cases)
    if size < config.min_cluster_animals:
        return []
    distances = array('f', [0.0]) * (size * size)
    neighbors = [[] for _ in cases]
    for left in range(size):
        for right in range(left + 1, size):
            distance = haversine_km(cases[left]['_coordinates'], cases[right]['_coordinates'])
            distances[left * size + right] = distances[right * size + left] = distance
            if distance <= config.radius_km and _agreement(cases[left]['_mask'], cases[right]['_mask']) >= config.similarity_threshold:
                neighbors[left].append(right)
                neighbors[right].append(left)
    remaining = set(range(size))
    result = []
    while len(remaining) >= config.min_cluster_animals:
        seed = min(remaining, key=lambda index: (-sum(other in remaining for other in neighbors[index]), cases[index]['_engine_id']))
        options = [index for index in neighbors[seed] if index in remaining]
        if len(options) + 1 < config.min_cluster_animals:
            break  # The densest remaining seed has insufficient evidence.
        options.sort(key=lambda index: (distances[seed * size + index], cases[index]['_observed'], cases[index]['_engine_id']))
        accepted = [seed]
        for candidate in options:
            if any(distances[candidate * size + member] > 2 * config.radius_km
                   or _agreement(cases[candidate]['_mask'], cases[member]['_mask']) < config.similarity_threshold for member in accepted):
                continue
            proposed = accepted + [candidate]
            center = _center([cases[index] for index in proposed])
            if all(haversine_km(center, cases[index]['_coordinates']) <= config.radius_km + 1e-9 for index in proposed):
                accepted.append(candidate)
        if len(accepted) >= config.min_cluster_animals:
            group = _score([cases[index] for index in accepted], baseline, now, config)
            if group['score'] >= config.abnormal_threshold:
                result.append(group)
                remaining.difference_update(accepted)
                continue
        remaining.remove(seed)
    return result


def detect_clusters(cases, baseline_cases, now, config=None):
    """Return preliminary flagged groups only; ungrouped cases remain isolated.

    Latest observations are chosen before rejection/unknown filtering. Closed
    cases retain their incident signal until they age out of the observation
    window. `now` is mandatory and timezone-aware for replay reproducibility.
    """
    config = config or OutbreakConfig()
    now = _time(now)
    if now is None:
        raise ValueError('Outbreak calculation time must be timezone-aware.')
    start = now - timedelta(hours=config.window_hours)
    active = _latest_animals(cases, start, now)
    if len(active) > config.max_cases:
        raise ValueError(f'Outbreak analysis exceeds {config.max_cases} active distinct animals; narrow the district/time scope.')
    baseline = _latest_animals(baseline_cases, start - timedelta(days=config.baseline_days), start, include_end=False)
    partitions = defaultdict(list)
    for case in active:
        partitions[(case.get('district', ''), case['_disease'])].append(case)
    groups = []
    for key in sorted(partitions):
        groups.extend(_partition_groups(partitions[key], baseline, now, config))
    return sorted(groups, key=lambda group: (-group['score'], group['case_ids']))
