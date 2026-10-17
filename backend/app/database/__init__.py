from datetime import datetime, timezone
from uuid import uuid4

from pymongo import ASCENDING, GEOSPHERE


def utcnow():
    value = datetime.now(timezone.utc)
    # BSON stores dates to millisecond precision; keep initial and retried API responses identical.
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def new_id():
    return str(uuid4())


def public(document):
    """Convert database IDs without leaking auth fields."""
    if document is None:
        return None
    result = dict(document)
    if '_id' in result:
        result['id'] = str(result.pop('_id'))
    for key in ('password_hash', 'payload_hash', 'animal_snapshot', 'workflow_operations'):
        result.pop(key, None)
    return result


def create_indexes(db):
    db.users.create_index('email', unique=True)
    db.users.create_index([('district', ASCENDING), ('role', ASCENDING)])
    db.sessions.create_index('expires_at', expireAfterSeconds=0)
    db.animals.create_index('pashu_id', unique=True)
    db.animals.create_index('owner_id')
    db.animals.create_index([('location', GEOSPHERE)])
    db.disease_cases.create_index([('reporter_id', ASCENDING), ('client_report_id', ASCENDING)], unique=True)
    db.disease_cases.create_index([('location', GEOSPHERE)])
    db.disease_cases.create_index([('district', ASCENDING), ('reported_at', ASCENDING)])
    db.disease_cases.create_index('animal_id')
    db.disease_cases.create_index('risk.level')
    db.disease_cases.create_index('triage.suspected_disease')
    db.disease_cases.create_index('status')
    db.media.create_index([('uploaded_by', ASCENDING), ('client_upload_id', ASCENDING)], unique=True)
    db.lab_tests.create_index('case_id')
    db.lab_tests.create_index('status')
    db.outbreak_clusters.create_index([('center', GEOSPHERE)])
    db.notifications.create_index('event_key', unique=True)
    db.audit_logs.create_index('created_at')


def audit(db, user_id, action, resource_id, details=None):
    db.audit_logs.insert_one({'_id': new_id(), 'user_id': user_id, 'action': action,
                             'resource_id': resource_id, 'details': details or {}, 'created_at': utcnow()})
