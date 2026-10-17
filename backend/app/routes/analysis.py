import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import authorized_document, current_user, get_db, roles
from app.config import ROOT
from app.database import utcnow
from app.schemas import ReportInput
from app.services.reports import analyze_observation

router = APIRouter()


@router.post('/triage')
def preview(payload: ReportInput, user=Depends(roles('farmer', 'paravet', 'vet', 'admin')), db=Depends(get_db)):
    animal = authorized_document(db, 'animals', payload.animal_id, user)
    triage, risk = analyze_observation(payload.model_dump(mode='json'), animal, payload.reported_at or utcnow())
    return {'triage': triage, 'risk': risk, 'saved': False}


@router.get('/risk/{report_id}')
def risk(report_id: str, user=Depends(current_user), db=Depends(get_db)):
    case = authorized_document(db, 'disease_cases', report_id, user)
    if not case.get('risk'):
        raise HTTPException(409, 'This earlier report has not yet been assessed.')
    return case['risk']


@router.get('/evaluation')
def evaluation(user=Depends(roles('admin', 'vet')), db=Depends(get_db)):
    path = ROOT / 'ml' / 'evaluation.json'
    metrics = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    outbreak_path = ROOT / 'ml' / 'outbreak_evaluation.json'
    outbreak = json.loads(outbreak_path.read_text(encoding='utf-8')) if outbreak_path.exists() else None
    return {'model': metrics, 'outbreak': outbreak, 'model_evaluation_available': metrics is not None,
            'limitations': 'Synthetic held-out evaluation is a software prototype check, not evidence of clinical accuracy.',
            'operational': {'unresolved_critical_cases': db.disease_cases.count_documents({
                'district': user['district'], 'status': {'$ne': 'closed'}, 'risk.level': 'CRITICAL'})}}
