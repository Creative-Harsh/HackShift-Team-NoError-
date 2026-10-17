from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import get_db, roles
from app.database import public
from app.schemas.workflow import Assignment, Review, SampleRequest, LabUpdate, CaseTransition
from app.services.workflow import mutate, repair_pending_workflows

router = APIRouter(tags=['Veterinary and laboratory care'])


@router.get('/vet/queue')
def queue(user=Depends(roles('vet')), db=Depends(get_db)):
    repair_pending_workflows(db, user['district'])
    return [public(c) for c in db.disease_cases.find({'district': user['district'], 'status': {'$ne': 'closed'},
        '$or': [{'needs_vet_review': True}, {'assigned_vet_id': user['_id']}]}).sort('risk.score', -1)]


@router.get('/users/veterinarians')
def vets(user=Depends(roles('vet', 'admin')), db=Depends(get_db)):
    return [public(c) for c in db.users.find({'district': user['district'], 'role': 'vet'}, {'name': 1, 'district': 1})]


@router.post('/cases/{case_id}/assign-vet')
def assign(case_id: str, payload: Assignment, request: Request, user=Depends(roles('vet', 'admin')), db=Depends(get_db)):
    return mutate(db, case_id, 'case.assign', payload, user, request.app.state.settings)


@router.put('/cases/{case_id}/vet-review')
def review(case_id: str, payload: Review, request: Request, user=Depends(roles('vet')), db=Depends(get_db)):
    return mutate(db, case_id, 'case.review', payload, user, request.app.state.settings)


@router.post('/cases/{case_id}/request-lab')
def sample(case_id: str, payload: SampleRequest, request: Request, user=Depends(roles('vet')), db=Depends(get_db)):
    return mutate(db, case_id, 'case.sample', payload, user, request.app.state.settings)


@router.put('/cases/{case_id}/status')
def transition(case_id: str, payload: CaseTransition, request: Request, user=Depends(roles('vet')), db=Depends(get_db)):
    return mutate(db, case_id, 'case.transition', payload, user, request.app.state.settings)


@router.get('/lab/requests')
def requests(user=Depends(roles('lab', 'vet', 'admin')), db=Depends(get_db)):
    repair_pending_workflows(db, user['district'])
    return [public(t) for t in db.lab_tests.find({'district': user['district']}).sort('requested_at', -1)]


@router.put('/lab/tests/{test_id}')
def result(test_id: str, payload: LabUpdate, request: Request, user=Depends(roles('lab')), db=Depends(get_db)):
    repair_pending_workflows(db, user['district'])
    test = db.lab_tests.find_one({'_id': test_id, 'district': user['district']})
    if not test:
        raise HTTPException(404, 'Test not found.')
    case = mutate(db, test['case_id'], 'lab.update', payload, user, request.app.state.settings, test_id)
    return {'case': case, 'test': public(db.lab_tests.find_one({'_id': test_id}))}
