"""Versioned case aggregates; lab/EHR/notification projections can be repaired on retry."""
from copy import deepcopy
import hashlib
import json
from threading import RLock

from fastapi import HTTPException
from app.auth import authorized_document
from app.database import new_id, public, utcnow
from app.notifications import notify
from app.services.records import refresh_animal_health

_lock = RLock()  # One API worker; distributed writers require leases/transactional projections.
FINAL_RESULTS = {'positive', 'negative', 'inconclusive'}


def reconcile_workflow(db, case_id):
    with _lock:
        case = db.disease_cases.find_one({'_id': case_id})
        if not case or not case.get('workflow_operations'):
            return
        for test in case.get('lab_tests', []):
            db.lab_tests.replace_one({'_id': test['id']}, {**test, '_id': test['id'], 'case_version': case['version']}, upsert=True)
        # Histories are projections of the authoritative case. Replace only this case's entries.
        animal = db.animals.find_one({'_id': case['animal_id']})
        if animal:
            histories = {}
            for field in ('disease_history', 'treatment_history', 'lab_history'):
                histories[field] = [entry for entry in animal.get(field, [])
                    if not (entry.get('source') == 'workflow' and entry.get('case_id') == case_id)]
            context = {'source': 'workflow', 'case_id': case_id, 'district': case['district']}
            if case.get('professional_review'):
                histories['disease_history'].append({**context, **case['professional_review'],
                    'confirmation_status': case['confirmation_status'], 'confirmed_disease': case.get('confirmed_disease')})
            for event in case['timeline']:
                if event['status'] == 'treatment':
                    histories['treatment_history'].append({**context, 'date': event['at'], 'note': event['note'], 'recorded_by': event['actor_id']})
            histories['lab_history'] += [{**context, **test} for test in case.get('lab_tests', [])]
            db.animals.update_one({'_id': animal['_id']}, {'$set': histories})
        for operation in case['workflow_operations']:
            db.audit_logs.update_one({'_id': 'workflow:' + operation['id']}, {'$setOnInsert': {
                'user_id': operation['actor_id'], 'action': operation['action'], 'resource_id': case_id,
                'district': case['district'], 'created_at': operation['at'], 'details': {'version': operation['version']}}}, upsert=True)
            notify(db, 'workflow:' + operation['id'], case['district'], 'Care workflow updated',
                f"{case['animal_name']}: {operation['state'].replace('_', ' ')}.", case_id=case_id,
                roles=('vet', 'admin', 'lab') if operation['state'] == 'sample_requested' else ('vet', 'admin'))
        refresh_animal_health(db, case['animal_id'])
        db.disease_cases.update_one({'_id': case_id, 'version': case['version']}, {'$set': {'projection_pending': False}})


def repair_pending_workflows(db, district):
    for case in db.disease_cases.find({'district': district, 'projection_pending': True}, {'_id': 1}):
        reconcile_workflow(db, case['_id'])


def mutate(db, case_id, action, payload, user, settings, test_id=None):
    with _lock:
        case = authorized_document(db, 'disease_cases', case_id, user)
        body = payload.model_dump(mode='json')
        digest = hashlib.sha256(json.dumps({'action': action, 'test_id': test_id, 'body': body}, sort_keys=True).encode()).hexdigest()
        existing = next((entry for entry in case.get('workflow_operations', []) if entry['id'] == body['operation_id']), None)
        if existing:
            if existing['hash'] != digest or existing['actor_id'] != user['_id']:
                raise HTTPException(409, 'Operation ID was already used with different information.')
            reconcile_workflow(db, case_id)
            from app.services.outbreaks import recalculate
            recalculate(db, case['district'], settings)
            return public(db.disease_cases.find_one({'_id': case_id}))
        if payload.expected_version != case['version']:
            raise HTTPException(409, 'This case changed. Refresh before submitting your update.')
        updated = deepcopy(case)
        now = utcnow()
        note = ''
        if action == 'case.assign':
            if user['role'] not in ('vet', 'admin'):
                raise HTTPException(403, 'Only a veterinarian or administrator can assign a case.')
            vet_id = payload.vet_id or user['_id']
            if user['role'] == 'vet' and (vet_id != user['_id'] or case.get('assigned_vet_id') not in (None, user['_id'])):
                raise HTTPException(403, 'Veterinarians can claim only unassigned cases or their own case.')
            vet = db.users.find_one({'_id': vet_id, 'role': 'vet', 'district': user['district']})
            if not vet:
                raise HTTPException(422, 'Choose a veterinarian in your district.')
            if case['status'] not in ('triage', 'vet_assigned', 'vet_review'):
                raise HTTPException(409, 'Assignment is unavailable at this stage.')
            updated.update(assigned_vet_id=vet_id, assigned_vet_name=vet['name'], assigned_at=case.get('assigned_at') or now, status='vet_assigned')
            note = 'Assigned to ' + vet['name'] + '; demo accounts do not imply live availability.'
        elif action == 'lab.update':
            if user['role'] != 'lab':
                raise HTTPException(403, 'Only laboratory operators can record laboratory results.')
            test = next((item for item in updated.get('lab_tests', []) if item['id'] == test_id), None)
            if not test or test['status'] in FINAL_RESULTS:
                raise HTTPException(409, 'This test is unavailable or its final result is immutable.')
            allowed = {'requested': {'received'}, 'received': {'testing'}, 'testing': FINAL_RESULTS}
            if payload.status not in allowed.get(test['status'], set()):
                raise HTTPException(409, 'Record sample receipt and testing before entering a result.')
            if payload.status in FINAL_RESULTS and len(payload.result_notes.strip()) < 3:
                raise HTTPException(422, 'A final result requires laboratory findings.')
            if payload.status == 'positive' and payload.confirmed_disease != test['disease_code']:
                raise HTTPException(422, 'Positive result must match the requested disease or syndrome category.')
            if payload.status != 'positive' and payload.confirmed_disease:
                raise HTTPException(422, 'Only a positive result can confirm the requested category.')
            if payload.attachment_url:
                media = db.media.find_one({'_id': payload.attachment_url.rsplit('/', 1)[-1], 'uploaded_by': user['_id'], 'kind': 'lab_report'})
                if not media:
                    raise HTTPException(422, 'Upload the laboratory report using your account first.')
            test.update(status=payload.status, updated_at=now, updated_by=user['_id'])
            if payload.status in FINAL_RESULTS:
                test.update(result_notes=payload.result_notes.strip(), confirmed_disease=payload.confirmed_disease,
                            attachment_url=payload.attachment_url, completed_at=now)
                state = {'positive': 'confirmed', 'negative': 'rejected', 'inconclusive': 'inconclusive'}[payload.status]
                updated.update(status=state, confirmation_status=state, confirmed_disease=payload.confirmed_disease)
            else:
                updated['status'] = 'lab_pending'
                test[payload.status + '_at'] = now
            note = f"Laboratory {payload.status}: {payload.result_notes.strip()}".rstrip(': ')
        else:
            if user['role'] != 'vet' or case.get('assigned_vet_id') != user['_id']:
                raise HTTPException(403, 'The assigned veterinarian must perform this action.')
            if action == 'case.review':
                if case['status'] not in ('vet_assigned', 'vet_review'):
                    raise HTTPException(409, 'Professional review is unavailable at this stage.')
                updated['professional_review'] = {'diagnosis': payload.diagnosis.strip(), 'recommendations': payload.recommendations.strip(),
                    'reviewed_by': user['_id'], 'reviewer_name': user['name'], 'date': now}
                updated['status'] = 'vet_review'
                note = 'Professional assessment recorded; laboratory confirmation remains separate.'
            elif action == 'case.sample':
                if case['status'] not in ('vet_review', 'inconclusive', 'rejected'):
                    raise HTTPException(409, 'Review the case before requesting a sample; only one pending test is allowed.')
                code = payload.disease_code or (case.get('triage') or {}).get('disease_code')
                if code not in ('lsd', 'fmd', 'respiratory', 'gastrointestinal'):
                    raise HTTPException(422, 'Specify the disease or syndrome category to investigate.')
                test = {'id': new_id(), 'case_id': case_id, 'animal_id': case['animal_id'], 'animal_name': case['animal_name'],
                    'pashu_id': case['pashu_id'], 'district': case['district'], 'village': case['village'],
                    'requested_by': user['_id'], 'requested_by_name': user['name'], 'requested_at': now, 'updated_at': now,
                    'test_type': payload.test_type.strip(), 'disease_code': code, 'notes': payload.notes.strip(), 'status': 'requested'}
                updated.setdefault('lab_tests', []).append(test)
                updated.update(status='sample_requested', confirmation_status='suspected', confirmed_disease=None)
                note = 'Sample requested: ' + payload.test_type.strip()
            elif action == 'case.transition':
                allowed = {'treatment': {'vet_review', 'confirmed', 'rejected', 'inconclusive'}, 'closed': {'treatment'}}
                if case['status'] not in allowed[payload.status]:
                    raise HTTPException(409, 'Complete professional review/results and control actions before closing; pending tests cannot be bypassed.')
                updated['status'] = payload.status
                note = payload.note.strip()
                if payload.status == 'closed':
                    updated['closed_at'] = now
            else:
                raise HTTPException(422, 'Unsupported workflow action.')
        updated.update(version=case['version'] + 1, updated_at=now, projection_pending=True)
        updated['timeline'].append({'status': updated['status'], 'at': now, 'actor_id': user['_id'], 'note': note})
        updated.setdefault('workflow_operations', []).append({'id': body['operation_id'], 'hash': digest, 'actor_id': user['_id'],
            'action': action, 'at': now, 'version': updated['version'], 'state': updated['status']})
        # Update only workflow-owned fields; simultaneous risk projections must not be overwritten.
        fields = ('assigned_vet_id', 'assigned_vet_name', 'assigned_at', 'status', 'confirmation_status', 'confirmed_disease',
            'professional_review', 'lab_tests', 'closed_at', 'version', 'updated_at', 'projection_pending', 'timeline', 'workflow_operations')
        changes = {key: updated[key] for key in fields if key in updated}
        result = db.disease_cases.update_one({'_id': case_id, 'version': payload.expected_version}, {'$set': changes})
        if not result.modified_count:
            raise HTTPException(409, 'A concurrent update changed this case. Refresh and retry.')
        reconcile_workflow(db, case_id)
        from app.services.outbreaks import recalculate
        recalculate(db, case['district'], settings)
        return public(db.disease_cases.find_one({'_id': case_id}))
