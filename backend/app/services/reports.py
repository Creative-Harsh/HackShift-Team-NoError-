from copy import deepcopy

import hashlib
import json

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.auth import authorized_document
from app.database import audit, new_id, public, utcnow
from app.services.records import reconcile_report


def analyze_observation(body, animal, observed_at):
    from app.triage import assess
    from app.risk_engine import calculate_risk
    triage = assess(body, animal, observed_at)
    risk = calculate_risk(body, animal, triage, now=observed_at)
    return triage, risk


def _project(db, case, settings):
    reconcile_report(db, case)
    if settings is not None:
        from app.services.outbreaks import recalculate
        recalculate(db, case['district'], settings)
    return public(db.disease_cases.find_one({'_id': case['_id']}))


def submit_report(db, payload, user, settings=None):
    animal = authorized_document(db, 'animals', payload.animal_id, user)
    body = payload.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    identity = {'reporter_id': user['_id'], 'client_report_id': str(payload.client_report_id)}
    existing = db.disease_cases.find_one(identity)
    if existing:
        if existing.get('payload_hash') != fingerprint:
            raise HTTPException(409, 'This report ID was already used with different information.')
        return _project(db, existing, settings), False
    for key in ('image_url', 'voice_note_url'):
        if body[key]:
            media_id = body[key].rsplit('/', 1)[-1]
            kind = 'image' if key == 'image_url' else 'voice_note'
            if not db.media.find_one({'_id': media_id, 'uploaded_by': user['_id'], 'kind': kind}):
                raise HTTPException(422, 'Attachment not found in your uploads.')
    now = utcnow()
    report_time = payload.reported_at or now
    triage, risk = analyze_observation(body, animal, report_time)
    case = {'_id': new_id(), **identity, 'payload_hash': fingerprint, 'animal_id': animal['_id'],
            'animal_name': animal['name'], 'pashu_id': animal['pashu_id'], 'species': animal['species'],
            'owner_id': animal['owner_id'], 'owner_name': animal['owner_name'],
            'animal_snapshot': deepcopy({key: animal.get(key) for key in ('species', 'age_months', 'gender', 'vaccination_history', 'disease_history')}),
            'district': animal['district'], 'village': animal['village'], 'reporter_role': user['role'],
            'report': body, 'location': body['location'], 'reported_at': report_time, 'created_at': now,
            'updated_at': now, 'status': 'triage', 'confirmation_status': 'suspected',
            'assigned_vet_id': None, 'triage': triage, 'risk': risk, 'initial_risk': risk,
            'needs_vet_review': risk['score'] >= 60 or triage['severity'].upper() in ('HIGH', 'CRITICAL'),
            'assessed_at': now, 'version': 1,
            'timeline': [{'status': 'reported', 'at': now, 'actor_id': user['_id'], 'note': 'Structured field report received.'},
                         {'status': 'triage', 'at': now, 'actor_id': 'system', 'note': 'Rules and structured model assessed this report; veterinary review remains required.'}]}
    try:
        db.disease_cases.insert_one(case)
    except DuplicateKeyError:
        original = db.disease_cases.find_one(identity)
        if original and original.get('payload_hash') == fingerprint:
            return _project(db, original, settings), False
        raise HTTPException(409, 'Conflicting duplicate report ID.')
    return _project(db, case, settings), True
