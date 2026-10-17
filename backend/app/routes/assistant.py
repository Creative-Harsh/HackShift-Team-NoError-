from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import current_user, get_db, roles
from app.assistant.schemas import ConcernInput, MessageInput, GuidanceResponse
from app.assistant.service import concern, respond

router = APIRouter(prefix='/assistant', tags=['PashuMitra read-only guidance'])
_events = OrderedDict()
_lock = Lock()


def limited(user=Depends(current_user)):
    now = monotonic()
    with _lock:
        events = _events.setdefault(user['_id'], deque())
        _events.move_to_end(user['_id'])
        while events and events[0] < now - 60:
            events.popleft()
        if len(events) >= 30:
            raise HTTPException(429, 'Please wait a minute before asking again.')
        events.append(now)
        while len(_events) > 2000:
            _events.popitem(last=False)
    return user


@router.get('/capabilities')
def capabilities(request: Request, user=Depends(current_user)):
    settings = request.app.state.settings
    return {'provider_available': bool(settings.gemini_api_key.get_secret_value() and settings.gemini_model),
            'languages': ['en', 'hi', 'hinglish'], 'record_mutation_tools': [], 'stores_transcripts': False}


@router.post('/message', response_model=GuidanceResponse)
def message(payload: MessageInput, request: Request, user=Depends(limited), db=Depends(get_db)):
    return respond(payload, user, db, request.app.state.settings)


@router.post('/concern')
def check_concern(payload: ConcernInput, user=Depends(limited), permitted=Depends(roles('farmer', 'paravet', 'vet', 'admin')), db=Depends(get_db)):
    return concern(payload, user, db)
