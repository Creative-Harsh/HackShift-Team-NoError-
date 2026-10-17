"""Derived district surveillance, stable cluster identities and current risk projections."""
from collections import Counter
from datetime import timedelta
from threading import RLock

from app.database import new_id, public, utcnow
from app.geospatial import haversine_km
from app.notifications import notify
from app.risk_engine import calculate_risk
from app.triage.context import vaccination_context

_district_lock = RLock()


def configuration(settings):
    from app.outbreak import OutbreakConfig
    return OutbreakConfig(radius_km=settings.outbreak_radius_km, window_hours=settings.outbreak_window_hours,
                          abnormal_threshold=settings.outbreak_abnormal_threshold,
                          suspected_threshold=settings.outbreak_suspected_threshold)


def recalculate(db, district, settings, now=None):
    """Synchronous, single-worker prototype projection. Case aggregates remain the source of truth.

    A retry rebuilds projections after an interrupted write. Run one API worker for this prototype;
    horizontal deployment needs a distributed job/lease rather than this process lock.
    """
    from app.outbreak import case_similarity, detect_clusters
    from app.outbreak.engine import incident_observations
    from fastapi import HTTPException
    now = now or utcnow()
    config = configuration(settings)
    with _district_lock:
        since = now - timedelta(hours=config.window_hours)
        historical_start = since - timedelta(days=config.baseline_days)
        base = {'district': district, 'triage': {'$ne': None}, 'reported_at': {'$gte': historical_start, '$lte': now}}
        if db.disease_cases.count_documents(base) > 5000:
            raise HTTPException(503, 'Surveillance capacity exceeded (5,000 observations). Report is stored; narrow the configured district/time window before recalculation.')
        observations = list(db.disease_cases.find(base).sort('reported_at', -1))
        animals = {a['_id']: a for a in db.animals.find({'district': district})}
        for case in observations:
            animal = case.get('animal_snapshot') or animals.get(case['animal_id'], {})
            case['effective_vaccination_status'] = vaccination_context(case['report'], animal,
                case['triage'].get('disease_code', 'undifferentiated'), case['reported_at'])['status']
        active = [c for c in observations if c['reported_at'] >= since]
        baseline = [c for c in observations if c['reported_at'] < since]
        try:
            groups = detect_clusters(active, baseline, now, config)
        except ValueError as error:
            raise HTTPException(503, str(error)) from error
        incident = incident_observations(active, since, now)
        previous = list(db.outbreak_clusters.find({'district': district}))
        claimed = set()
        saved_ids = []
        for group in groups:
            members = set(group['case_ids'])
            candidates = []
            for old in previous:
                if old['_id'] in claimed or old.get('disease_code') != group['disease_code']:
                    continue
                old_members = set(old['case_ids'])
                overlap = len(members & old_members) / max(1, min(len(members), len(old_members)))
                if overlap >= .5:
                    candidates.append((overlap, old))
            old = max(candidates, key=lambda item: (item[0], item[1]['_id']))[1] if candidates else None
            identifier = old['_id'] if old else new_id()
            claimed.add(identifier)
            computed_status = group['status']
            group.update({'_id': identifier, 'active': True, 'computed_status': computed_status,
                          'created_at': old['created_at'] if old else now, 'updated_at': now})
            if old and old.get('confirmed_at'):
                # Confirmation is historical professional evidence, never overwritten by the algorithm.
                for key in ('confirmed_at', 'confirmed_by', 'confirmation_note', 'evidence_test_ids'):
                    if key in old:
                        group[key] = old[key]
                group['status'] = 'confirmed_outbreak'
            db.outbreak_clusters.replace_one({'_id': identifier}, group, upsert=True)
            saved_ids.append(identifier)
            event_key = f"cluster:{identifier}:{computed_status}:{group['level']}"
            notify(db, event_key, district, 'Abnormal local disease activity',
                   f"{group['animal_count']} distinct animals: {group['suspected_disease']}. Cluster score {group['score']}/100; professional investigation required.",
                   cluster_id=identifier)
        db.outbreak_clusters.update_many({'district': district, '_id': {'$nin': saved_ids}},
                                         {'$set': {'active': False, 'updated_at': now}})
        # Cluster evidence does not use risk. Feed spatial evidence back to case risk only after grouping.
        expired_context = list(db.disease_cases.find({'district': district, 'reported_at': {'$lt': since},
            '$or': [{'nearby_similar_animals': {'$gt': 0}}, {'cluster_score': {'$gt': 0}}]}))
        for case in active + expired_context:
            animal = case.get('animal_snapshot') or animals.get(case['animal_id'])
            if not animal:
                continue
            neighbors = set()
            for other in (incident if case['reported_at'] >= since else []):
                if other['animal_id'] == case['animal_id'] or other.get('confirmation_status') == 'rejected':
                    continue
                if case_similarity(case, other) >= .75 and haversine_km(case['location']['coordinates'], other['location']['coordinates']) <= config.radius_km:
                    neighbors.add(other['animal_id'])
            cluster_score = max((g['score'] for g in groups if case['_id'] in g['case_ids']), default=0)
            risk = calculate_risk(case['report'], animal, case['triage'], nearby_count=len(neighbors), cluster_score=cluster_score,
                                  now=case['reported_at'])
            needs_vet = risk['score'] >= 60 or case['triage'].get('severity', 'moderate').upper() in ('HIGH', 'CRITICAL')
            db.disease_cases.update_one({'_id': case['_id']}, {'$set': {'risk': risk, 'risk_updated_at': now,
                'nearby_similar_animals': len(neighbors), 'cluster_score': cluster_score, 'needs_vet_review': needs_vet}})
            if needs_vet and case['status'] != 'closed':
                notify(db, f"case-priority:{case['_id']}:{risk['level']}", district, 'Veterinary review recommended',
                       f"{case['animal_name']}: {case['triage']['suspected_disease']}; risk {risk['score']}/100.", case_id=case['_id'])
        db.surveillance_runs.update_one({'_id': district}, {'$set': {'calculated_at': now}}, upsert=True)
        return [cluster_view(db, c) for c in db.outbreak_clusters.find({'_id': {'$in': saved_ids}})]


def cluster_view(db, cluster):
    item = public(cluster)
    cases = list(db.disease_cases.find({'_id': {'$in': cluster['case_ids']}}).sort('reported_at', -1))
    counts = Counter(c['risk']['level'] for c in cases if c.get('risk'))
    item['risk_distribution'] = {level: counts.get(level, 0) for level in ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')}
    item['latest_reports'] = [public(c) for c in cases[:5]]
    return item


def refresh_if_stale(db, district, settings):
    """Polling expires incident evidence even when no new reports arrive."""
    with _district_lock:
        last = db.surveillance_runs.find_one({'_id': district})
        if not last or (utcnow() - last['calculated_at']).total_seconds() >= 30:
            recalculate(db, district, settings)
