from app.database import utcnow


def refresh_animal_health(db, animal_id):
    """Idempotent projection of current case state; duplicate reports cannot reopen closed episodes."""
    active = db.disease_cases.count_documents({'animal_id': animal_id, 'status': {'$ne': 'closed'}})
    db.animals.update_one({'_id': animal_id}, {'$set': {'health_status': 'under_observation' if active else 'healthy', 'updated_at': utcnow()}})


def reconcile_report(db, case):
    refresh_animal_health(db, case['animal_id'])
    db.audit_logs.update_one({'_id': 'report-created:' + case['_id']}, {'$setOnInsert': {
        'user_id': case['reporter_id'], 'action': 'report.create', 'resource_id': case['_id'],
        'details': {}, 'created_at': case['created_at']}}, upsert=True)
