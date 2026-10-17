from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import current_user, get_db, roles, scope
from app.database import public, utcnow
from app.geospatial import nearby_query
from app.services.outbreaks import cluster_view, recalculate, refresh_if_stale

router = APIRouter()
DISEASES = {'lsd', 'fmd', 'respiratory', 'gastrointestinal', 'undifferentiated'}


@router.get('/cases/nearby')
def nearby(longitude: Annotated[float, Query(ge=-180, le=180)], latitude: Annotated[float, Query(ge=-90, le=90)],
           radius_km: Annotated[float, Query(gt=0, le=100)] = 5,
           days: Annotated[int, Query(ge=1, le=365)] = 3, disease: str | None = None,
           user=Depends(roles('farmer', 'paravet', 'vet', 'admin')), db=Depends(get_db)):
    query = scope(user, 'disease_cases')
    if disease:
        if disease not in DISEASES:
            raise HTTPException(422, 'Choose a supported disease code.')
        query['triage.disease_code'] = disease
    query = nearby_query(longitude, latitude, radius_km, utcnow() - timedelta(days=days), query)
    return [public(c) for c in db.disease_cases.find(query).limit(1000)]


@router.get('/outbreaks/map')
def map_data(request: Request, days: Annotated[int, Query(ge=1, le=365)] = 3, disease: str | None = None,
             species: str | None = None, village: str | None = None, district: str | None = None,
             user=Depends(roles('paravet', 'vet', 'admin')), db=Depends(get_db)):
    if district and district != user['district']:
        raise HTTPException(403, 'This district is outside your authorized scope.')
    refresh_if_stale(db, user['district'], request.app.state.settings)
    query = {'district': user['district'], 'reported_at': {'$gte': utcnow() - timedelta(days=days), '$lte': utcnow()}}
    if disease:
        if disease not in DISEASES:
            raise HTTPException(422, 'Choose a supported disease code.')
        query['triage.disease_code'] = disease
    if species:
        query['species'] = species
    if village:
        query['village'] = village
    total = db.disease_cases.count_documents(query)
    cases = list(db.disease_cases.find(query).sort('reported_at', -1).limit(2000))
    visible = {c['_id'] for c in cases}
    clusters = [cluster_view(db, c) for c in db.outbreak_clusters.find({'district': user['district'], 'active': True})
                if set(c['case_ids']) & visible]
    settings = request.app.state.settings
    return {'cases': [public(c) for c in cases], 'clusters': clusters, 'total_cases': total, 'truncated': total > len(cases),
            'config': {'radius_km': settings.outbreak_radius_km, 'window_hours': settings.outbreak_window_hours}, 'generated_at': utcnow()}


@router.get('/outbreaks')
def clusters(request: Request, user=Depends(roles('paravet', 'vet', 'admin')), db=Depends(get_db)):
    refresh_if_stale(db, user['district'], request.app.state.settings)
    return [cluster_view(db, c) for c in db.outbreak_clusters.find({'district': user['district'], 'active': True}).sort('score', -1)]


@router.post('/outbreaks/recalculate')
def refresh(request: Request, user=Depends(roles('vet', 'admin')), db=Depends(get_db)):
    return {'clusters': recalculate(db, user['district'], request.app.state.settings)}


@router.get('/outbreaks/{cluster_id}')
def detail(cluster_id: str, user=Depends(roles('paravet', 'vet', 'admin')), db=Depends(get_db)):
    cluster = db.outbreak_clusters.find_one({'_id': cluster_id, 'district': user['district']})
    if not cluster:
        raise HTTPException(404, 'Cluster not found.')
    return cluster_view(db, cluster)
