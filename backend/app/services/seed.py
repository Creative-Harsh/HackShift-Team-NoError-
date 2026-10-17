"""Idempotent, explicitly synthetic demo identity/EHR records. No government data."""
from datetime import timedelta

from app.auth import password_hasher
from app.database import utcnow

DEMO_PASSWORD = 'Demo@26128'


def seed_demo(db):
    now = utcnow()
    people = [('farmer', 'Savita Patil'), ('paravet', 'Anil Shinde'), ('vet', 'Dr. Meera Joshi'),
              ('lab', 'Rohan Deshmukh'), ('admin', 'District Surveillance Officer')]
    password_hash = None
    for role, name in people:
        email = f'{role}@demo.pashuraksha.in'
        if not db.users.find_one({'email': email}):
            password_hash = password_hash or password_hasher.hash(DEMO_PASSWORD)
            db.users.insert_one({'_id': f'demo-{role}', 'name': name, 'email': email, 'role': role,
                                 'district': 'Pune', 'password_hash': password_hash, 'created_at': now, 'is_demo': True})
    if not db.users.find_one({'_id': 'demo-farmer-b'}):
        password_hash = password_hash or password_hasher.hash(DEMO_PASSWORD)
        db.users.insert_one({'_id': 'demo-farmer-b', 'name': 'Ganesh Jadhav', 'email': 'farmer2@demo.pashuraksha.in',
                             'role': 'farmer', 'district': 'Pune', 'password_hash': password_hash, 'created_at': now, 'is_demo': True})
    villages = [('Shirgaon', 73.675, 18.722), ('Somatane', 73.704, 18.711), ('Talegaon', 73.682, 18.751)]
    for i in range(18):
        village, lon, lat = villages[(i // 6) % 3]
        species = ['cattle', 'buffalo', 'goat'][i % 3] if i >= 12 else 'cattle'
        owner_id = 'demo-farmer' if i % 2 == 0 else 'demo-farmer-b'
        owner_name = 'Savita Patil' if i % 2 == 0 else 'Ganesh Jadhav'
        item = {'_id': f'demo-animal-{i + 1:02}', 'pashu_id': f'26128000{i + 1:04}',
                'name': ['Gauri', 'Lakshmi', 'Moti', 'Champa', 'Nandi', 'Tara'][i % 6] + (f' {i // 6 + 1}' if i >= 6 else ''),
                'species': species, 'breed': {'cattle': 'Gir', 'buffalo': 'Murrah', 'goat': 'Osmanabadi'}[species],
                'age_months': 9 if i == 0 else 24 + i * 2, 'gender': 'female', 'owner_id': owner_id, 'owner_name': owner_name,
                'location': {'type': 'Point', 'coordinates': [lon + (i % 6) * .001, lat + (i % 6) * .0005]},
                'village': village, 'district': 'Pune', 'health_status': 'healthy', 'created_at': now,
                'updated_at': now, 'is_demo': True,
                'vaccination_history': [{'id': f'demo-vax-{i}', 'vaccine': 'LSD' if species in ('cattle', 'buffalo') else 'FMD',
                    'date_given': (now - timedelta(days=420 if i < 12 else 60)).date().isoformat(),
                    'next_due_date': (now + timedelta(days=-55 if i < 12 else 305)).date().isoformat(), 'recorded_by': 'demo-paravet'}],
                'disease_history': [], 'treatment_history': [], 'lab_history': []}
        db.animals.update_one({'_id': item['_id']}, {'$setOnInsert': item}, upsert=True)
