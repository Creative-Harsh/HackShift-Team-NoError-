import json
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from app.auth import get_db, roles, current_user
from app.config import ROOT
from app.database import audit, public, utcnow
from app.schemas import StrictModel
from app.services.outbreaks import cluster_view, refresh_if_stale
from app.services.workflow import repair_pending_workflows

router = APIRouter(tags=['District surveillance'])


def series(counter):
    return [{'name': key, 'count': value} for key, value in sorted(counter.items())]


@router.get('/admin/dashboard')
def dashboard(request: Request, user=Depends(roles('admin')), db=Depends(get_db)):
    repair_pending_workflows(db, user['district'])
    refresh_if_stale(db, user['district'], request.app.state.settings)
    query = {'district': user['district']}
    cases = list(db.disease_cases.find(query))
    active = [c for c in cases if c['status'] != 'closed']
    clusters = list(db.outbreak_clusters.find({**query, 'active': True}))
    now = utcnow()
    recent = [c for c in cases if now - timedelta(days=30) <= c['reported_at'] <= now]
    daily = Counter(c['reported_at'].date().isoformat() for c in recent)
    days = [(now - timedelta(days=offset)).date().isoformat() for offset in reversed(range(30))]
    assignment = [(c['assigned_at'] - c['created_at']).total_seconds() / 60 for c in cases if c.get('assigned_at')]
    return {'generated_at': now, 'kpis': {
        'total_animals': db.animals.count_documents(query), 'active_cases': len(active),
        'high_risk_cases': sum((c.get('risk') or {}).get('score', 0) >= 60 for c in active),
        'critical_cases': sum((c.get('risk') or {}).get('level') == 'CRITICAL' for c in active),
        'suspected_outbreaks': sum(c['status'] == 'suspected_outbreak' for c in clusters),
        'confirmed_outbreaks': sum(c['status'] == 'confirmed_outbreak' for c in clusters)},
        'cases_over_time': [{'name': day, 'count': daily[day]} for day in days],
        'disease_distribution': series(Counter((c.get('triage') or {}).get('suspected_disease', 'Unassessed') for c in recent)),
        'species_distribution': series(Counter(c['species'] for c in recent)),
        'risk_distribution': series(Counter((c.get('risk') or {}).get('level', 'Unassessed') for c in recent)),
        'critical_cases': [public(c) for c in sorted(active, key=lambda c: c['created_at']) if (c.get('risk') or {}).get('level') == 'CRITICAL'],
        'recent_clusters': [cluster_view(db, c) for c in sorted(clusters, key=lambda c: -c['score'])],
        'operational': {'mean_report_to_assignment_minutes': sum(assignment) / len(assignment) if assignment else None,
                        'assigned_case_count': len(assignment)},
        'analytics_period_days': 30}


class Confirmation(StrictModel):
    evidence_test_ids: list[str] = Field(min_length=1, max_length=30)
    note: str = Field(min_length=10, max_length=2000)


@router.post('/outbreaks/{cluster_id}/confirm')
def confirm(cluster_id: str, payload: Confirmation, request: Request, user=Depends(roles('admin')), db=Depends(get_db)):
    from app.services.workflow import _lock
    from app.services.outbreaks import _district_lock, recalculate
    # Use the same lock order as case mutations, so membership/evidence and an
    # explicit confirmation cannot race with a projection replacement.
    with _lock, _district_lock:
        repair_pending_workflows(db, user['district'])
        recalculate(db, user['district'], request.app.state.settings)
        return confirm_evidence(db, cluster_id, payload, user)


def confirm_evidence(db, cluster_id, payload, user):
    cluster = db.outbreak_clusters.find_one({'_id': cluster_id, 'district': user['district']})
    if not cluster:
        raise HTTPException(404, 'Cluster not found.')
    if cluster.get('confirmed_at'):
        if set(cluster.get('evidence_test_ids', [])) == set(payload.evidence_test_ids) and cluster.get('confirmation_note') == payload.note:
            return cluster_view(db, cluster)
        raise HTTPException(409, 'Confirmation is already recorded and cannot be silently replaced.')
    if not cluster.get('active'):
        raise HTTPException(409, 'Investigate an active cluster before confirming an outbreak.')
    for identifier in set(payload.evidence_test_ids):
        test = db.lab_tests.find_one({'_id': identifier, 'district': user['district'], 'status': 'positive',
            'confirmed_disease': cluster['disease_code'], 'case_id': {'$in': cluster['case_ids']}})
        # Verify current aggregate as well as projection: a superseding rejected test cannot confirm an outbreak.
        case = db.disease_cases.find_one({'_id': test['case_id']}) if test else None
        if not test or not case or case.get('confirmation_status') != 'confirmed' or case.get('confirmed_disease') != cluster['disease_code']:
            raise HTTPException(422, 'Evidence must be a positive matching laboratory test for a currently confirmed case in this cluster.')
    now = utcnow()
    result = db.outbreak_clusters.update_one({'_id': cluster_id, 'confirmed_at': {'$exists': False}}, {'$set': {
        'status': 'confirmed_outbreak', 'confirmed_at': now, 'confirmed_by': user['_id'],
        'confirmation_note': payload.note, 'evidence_test_ids': sorted(set(payload.evidence_test_ids))}})
    if not result.modified_count:
        raise HTTPException(409, 'This cluster changed; refresh it before continuing.')
    audit(db, user['_id'], 'outbreak.confirm', cluster_id, {'evidence_test_ids': payload.evidence_test_ids, 'note': payload.note})
    return cluster_view(db, db.outbreak_clusters.find_one({'_id': cluster_id}))


@router.get('/notifications')
def notifications(user=Depends(current_user), db=Depends(get_db)):
    return [public(n) for n in db.notifications.find({'district': user['district'], 'roles': user['role']}).sort('created_at', -1).limit(100)]


@router.post('/notifications/{notification_id}/read')
def mark_read(notification_id: str, user=Depends(current_user), db=Depends(get_db)):
    result = db.notifications.update_one({'_id': notification_id, 'district': user['district'], 'roles': user['role']}, {'$addToSet': {'read_by': user['_id']}})
    if not result.matched_count:
        raise HTTPException(404, 'Notification not found.')
    return {'read': True}


@router.get('/admin/audit')
def audit_log(user=Depends(roles('admin')), db=Depends(get_db)):
    case_ids = db.disease_cases.distinct('_id', {'district': user['district']})
    cluster_ids = db.outbreak_clusters.distinct('_id', {'district': user['district']})
    return [public(e) for e in db.audit_logs.find({'resource_id': {'$in': case_ids + cluster_ids}}).sort('created_at', -1).limit(100)]
