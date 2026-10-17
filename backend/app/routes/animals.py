import secrets

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.auth import authorized_document, current_user, get_db, roles, scope
from app.database import audit, new_id, public, utcnow
from app.schemas import AnimalInput, VaccinationInput

router = APIRouter()


@router.get('/animals')
def animals(user=Depends(current_user), db=Depends(get_db)):
    query = scope(user)
    if user['role'] == 'lab':
        case_ids = db.lab_tests.distinct('case_id', {'district': user['district']})
        query['_id'] = {'$in': db.disease_cases.distinct('animal_id', {'_id': {'$in': case_ids}})}
    records = list(db.animals.find(query).sort('created_at', -1).limit(1000))
    if user['role'] == 'lab':
        records = [authorized_document(db, 'animals', a['_id'], user) for a in records]
    return [public(a) for a in records]


@router.get('/animals/pashu-id/{pashu_id}')
def lookup(pashu_id: str, user=Depends(current_user), db=Depends(get_db)):
    if len(pashu_id) != 12 or not pashu_id.isdigit():
        raise HTTPException(422, 'Enter a 12-digit simulated Pashu Aadhaar.')
    animal = db.animals.find_one({'pashu_id': pashu_id, **scope(user)})
    if not animal:
        raise HTTPException(404, 'Animal not found in your accessible records.')
    return public(authorized_document(db, 'animals', animal['_id'], user))


def owner_for(payload, user, db):
    owner_id = payload.owner_id or user['_id']
    if user['role'] == 'farmer' and owner_id != user['_id']:
        raise HTTPException(403, 'Farmers can register only their own animals.')
    if payload.district != user['district']:
        raise HTTPException(403, 'Animal must be in your assigned district.')
    owner = db.users.find_one({'_id': owner_id, 'role': 'farmer', 'district': user['district']})
    if not owner:
        raise HTTPException(422, 'Choose a farmer owner in your district.')
    return owner


@router.post('/animals', status_code=201)
def create_animal(payload: AnimalInput, user=Depends(roles('farmer', 'paravet')), db=Depends(get_db)):
    owner = owner_for(payload, user, db)
    item = payload.model_dump(mode='json')
    item.update({'_id': new_id(), 'owner_id': owner['_id'], 'owner_name': owner['name'],
                 'pashu_id': payload.pashu_id or str(secrets.randbelow(900000000000) + 100000000000),
                 'vaccination_history': [], 'disease_history': [], 'treatment_history': [], 'lab_history': [],
                 'health_status': 'healthy', 'created_at': utcnow(), 'updated_at': utcnow()})
    try:
        db.animals.insert_one(item)
    except DuplicateKeyError:
        raise HTTPException(409, 'This simulated Pashu Aadhaar is already registered.')
    audit(db, user['_id'], 'animal.create', item['_id'])
    return public(item)


@router.get('/animals/{animal_id}')
def detail(animal_id: str, user=Depends(current_user), db=Depends(get_db)):
    return public(authorized_document(db, 'animals', animal_id, user))


@router.put('/animals/{animal_id}')
def update(animal_id: str, payload: AnimalInput, user=Depends(roles('farmer', 'paravet')), db=Depends(get_db)):
    existing = authorized_document(db, 'animals', animal_id, user)
    owner = owner_for(payload, user, db)
    if owner['_id'] != existing['owner_id']:
        raise HTTPException(409, 'Ownership transfer requires a separate verified process.')
    if payload.pashu_id and payload.pashu_id != existing['pashu_id']:
        raise HTTPException(409, 'Animal identity cannot be changed after registration.')
    changes = payload.model_dump(mode='json', exclude={'owner_id', 'pashu_id'})
    changes['updated_at'] = utcnow()
    db.animals.update_one({'_id': animal_id}, {'$set': changes})
    audit(db, user['_id'], 'animal.update', animal_id)
    return public(db.animals.find_one({'_id': animal_id}))


@router.get('/animals/{animal_id}/history')
def history(animal_id: str, user=Depends(current_user), db=Depends(get_db)):
    animal = authorized_document(db, 'animals', animal_id, user)
    query = {'animal_id': animal_id}
    if user['role'] == 'lab':
        query['_id'] = {'$in': db.lab_tests.distinct('case_id', {'district': user['district']})}
    cases = list(db.disease_cases.find(query).sort('reported_at', -1))
    tests_query = {'case_id': {'$in': [c['_id'] for c in cases]}}
    if user['role'] == 'lab':
        tests_query['district'] = user['district']
    return {'animal': public(animal), 'cases': [public(c) for c in cases],
            'lab_tests': [public(t) for t in db.lab_tests.find(tests_query)]}


@router.post('/animals/{animal_id}/vaccinations')
def vaccination(animal_id: str, payload: VaccinationInput, user=Depends(roles('paravet', 'vet')), db=Depends(get_db)):
    authorized_document(db, 'animals', animal_id, user)
    entry = {**payload.model_dump(mode='json'), 'id': new_id(), 'recorded_by': user['_id']}
    db.animals.update_one({'_id': animal_id}, {'$push': {'vaccination_history': entry}, '$set': {'updated_at': utcnow()}})
    audit(db, user['_id'], 'vaccination.record', animal_id)
    return public(db.animals.find_one({'_id': animal_id}))
