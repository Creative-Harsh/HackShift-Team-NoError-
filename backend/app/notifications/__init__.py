from app.database import utcnow


def notify(db, event_key, district, title, message, roles=('vet', 'admin'), case_id=None, cluster_id=None):
    """In-app events only. No SMS/email/government connection is implied."""
    item = {'event_key': event_key, 'district': district, 'roles': list(roles), 'title': title,
            'message': message, 'case_id': case_id, 'cluster_id': cluster_id, 'created_at': utcnow(), 'read_by': []}
    db.notifications.update_one({'event_key': event_key}, {'$setOnInsert': item}, upsert=True)
