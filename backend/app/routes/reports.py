from fastapi import APIRouter, Depends, Response

from app.auth import authorized_document, current_user, get_db, roles, scope
from app.database import public
from app.schemas import ReportInput
from app.services.reports import submit_report
from fastapi import Request

router = APIRouter()


@router.post('/reports', status_code=201)
def report(payload: ReportInput, response: Response, request: Request, user=Depends(roles('farmer', 'paravet')), db=Depends(get_db)):
    result, created = submit_report(db, payload, user, request.app.state.settings)
    response.status_code = 201 if created else 200
    return result


@router.get('/cases')
def cases(user=Depends(current_user), db=Depends(get_db)):
    query = scope(user, 'disease_cases')
    if user['role'] == 'lab':
        query['_id'] = {'$in': db.lab_tests.distinct('case_id', {'district': user['district']})}
    return [public(c) for c in db.disease_cases.find(query).sort('reported_at', -1).limit(2000)]


@router.get('/cases/{case_id}')
def case(case_id: str, user=Depends(current_user), db=Depends(get_db)):
    return public(authorized_document(db, 'disease_cases', case_id, user))


@router.get('/reports/{report_id}')
def get_report(report_id: str, user=Depends(current_user), db=Depends(get_db)):
    return public(authorized_document(db, 'disease_cases', report_id, user))
