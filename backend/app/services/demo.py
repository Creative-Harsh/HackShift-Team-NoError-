"""Explicit synthetic replay. All case evidence uses the normal reporting engine."""
from datetime import timedelta
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException

from app.database import audit, new_id, utcnow
from app.schemas import ReportInput
from app.services.outbreaks import recalculate
from app.services.reports import submit_report

_lock = RLock()
TOTAL = 11


def status(db, user, settings):
    run = db.demo_runs.find_one({'_id': 'outbreak-v1:' + user['district']})
    return {'enabled': settings.demo_mode, 'completed': run['completed'] if run else 0,
            'total': TOTAL, 'run_id': run['run_id'] if run else None,
            'label': 'Synthetic outbreak demonstration; no government or field surveillance data.'}


def replay(db, user, settings, steps):
    if not settings.demo_mode:
        raise HTTPException(403, 'Demo replay is disabled in this environment.')
    if user['district'] != 'Pune':
        raise HTTPException(409, 'The synthetic replay is configured for the Pune demo district.')
    with _lock:
        identity = 'outbreak-v1:' + user['district']
        db.demo_runs.update_one({'_id': identity}, {'$setOnInsert': {
            'run_id': new_id(), 'completed': 0, 'origin_time': utcnow()}}, upsert=True)
        run = db.demo_runs.find_one({'_id': identity})
        now = run['origin_time']
        reporter = db.users.find_one({'_id': 'demo-paravet', 'is_demo': True})
        if not reporter:
            raise HTTPException(409, 'Seed the demo accounts before replaying the scenario.')
        for index in range(12):
            village, lon, lat = ('Shirgaon', 73.675, 18.722) if index < 7 or index == 11 else ('Somatane', 73.704, 18.711)
            animal = {'_id': f'outbreak-demo-animal-{index + 1:02}', 'pashu_id': f'26128100{index + 1:04}',
                'name': f'Demo herd animal {index + 1}', 'species': 'cattle', 'breed': 'Gir',
                'age_months': 9 if index == 0 else 36, 'gender': 'female',
                'owner_id': 'demo-farmer' if index % 2 == 0 else 'demo-farmer-b',
                'owner_name': 'Savita Patil' if index % 2 == 0 else 'Ganesh Jadhav',
                'location': {'type': 'Point', 'coordinates': [lon + (index % 7) * .0005, lat + (index % 7) * .0003]},
                'district': 'Pune', 'village': village, 'is_demo': True, 'health_status': 'healthy',
                'vaccination_history': [{'id': f'replay-vax-{index}', 'vaccine': 'LSD',
                    'date_given': (now - timedelta(days=420)).date().isoformat(),
                    'next_due_date': (now - timedelta(days=55)).date().isoformat(), 'recorded_by': reporter['_id']}],
                'disease_history': [], 'treatment_history': [], 'lab_history': [], 'created_at': now, 'updated_at': now}
            db.animals.update_one({'_id': animal['_id']}, {'$setOnInsert': animal}, upsert=True)

        def observation(index, hours):
            animal = db.animals.find_one({'_id': f'outbreak-demo-animal-{index + 1:02}'})
            return ReportInput(client_report_id=uuid5(NAMESPACE_URL, run['run_id'] + ':' + str(index)),
                animal_id=animal['_id'], symptoms=['fever', 'skin_lesions', 'swelling'], temperature_c=40.2,
                appetite='reduced', milk_drop_percent=25, activity='reduced', recent_contact=True,
                vaccination_status='overdue', mortality_count=0, duration_hours=24, location=animal['location'],
                reported_at=now - timedelta(hours=hours))

        baseline, _ = submit_report(db, observation(11, 14 * 24), reporter)
        db.disease_cases.update_one({'_id': baseline['id']}, {'$set': {'status': 'closed', 'is_demo': True,
            'demo_run_id': run['run_id']}, '$addToSet': {'timeline': {'status': 'closed', 'at': now,
                'actor_id': 'demo-seeder', 'note': 'Synthetic historical baseline; closed episode.'}}})
        from app.services.records import refresh_animal_health
        refresh_animal_health(db, baseline['animal_id'])
        ages = [48, 42, 36, 30, 24, 18, 12, 9, 6, 3, 0]
        new_cases = []
        for index in range(run['completed'], min(TOTAL, run['completed'] + steps)):
            case, created = submit_report(db, observation(index, ages[index]), reporter, settings)
            db.disease_cases.update_one({'_id': case['id']}, {'$set': {'is_demo': True, 'demo_run_id': run['run_id']}})
            db.demo_runs.update_one({'_id': identity}, {'$set': {'completed': index + 1}})
            if created:
                new_cases.append(case['id'])
                audit(db, user['_id'], 'demo.replay', case['id'], {'run_id': run['run_id'], 'step': index + 1})
        return {**status(db, user, settings), 'new_case_ids': new_cases,
                'clusters': recalculate(db, user['district'], settings)}
