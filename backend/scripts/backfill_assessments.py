"""One-time local demo migration for reports created before the intelligence phase."""
from pymongo import MongoClient
from app.config import get_settings
from app.database import audit, utcnow
from app.services.reports import analyze_observation


def backfill(db):
    updated = 0
    for case in db.disease_cases.find({'triage': None}):
        animal = db.animals.find_one({'_id': case['animal_id']})
        if not animal:
            continue
        triage, risk = analyze_observation(case['report'], animal, case['reported_at'])
        now = utcnow()
        changes = {'triage': triage, 'risk': risk, 'initial_risk': risk, 'assessed_at': now,
                   'needs_vet_review': risk['score'] >= 60 or triage['severity'].upper() in ('HIGH', 'CRITICAL')}
        if case['status'] == 'reported':
            changes['status'] = 'triage'
        result = db.disease_cases.update_one({'_id': case['_id'], 'triage': None}, {'$set': changes,
            '$push': {'timeline': {'status': 'triage', 'at': now, 'actor_id': 'demo-migration', 'note': 'Previously unassessed development report evaluated by the structured engine.'}}})
        if result.modified_count:
            audit(db, 'demo-migration', 'case.assessment_backfill', case['_id'])
            updated += 1
    return updated


if __name__ == '__main__':
    settings = get_settings()
    if not settings.demo_mode:
        raise SystemExit('This helper is restricted to DEMO_MODE.')
    with MongoClient(settings.mongodb_uri, tz_aware=True) as client:
        print('Previously unassessed demo reports evaluated:', backfill(client[settings.mongodb_database]))
