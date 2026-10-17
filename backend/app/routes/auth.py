from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from app.auth import DUMMY_HASH, current_user, get_db, issue_token, password_hasher, roles
from app.database import audit, new_id, public, utcnow
from app.schemas import Login, Register

router = APIRouter()
_attempts = defaultdict(deque)
_lock = Lock()


def rate_limit(request):
    key = request.client.host if request.client else 'unknown'
    now = monotonic()
    with _lock:
        events = _attempts[key]
        while events and events[0] < now - 60:
            events.popleft()
        if len(events) >= 30:
            raise HTTPException(429, 'Too many sign-in attempts. Try again in one minute.', headers={'Retry-After': '60'})
        events.append(now)


@router.post('/auth/register', status_code=201)
def register(payload: Register, request: Request, db=Depends(get_db)):
    rate_limit(request)
    user = {'_id': new_id(), 'name': payload.name, 'email': str(payload.email).lower(),
            'password_hash': password_hasher.hash(payload.password), 'district': payload.district,
            'role': 'farmer', 'created_at': utcnow()}
    try:
        db.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(409, 'An account with this email already exists.')
    audit(db, user['_id'], 'auth.register', user['_id'])
    return issue_token(db, user, request.app.state.settings)


@router.post('/auth/login')
def login(payload: Login, request: Request, db=Depends(get_db)):
    rate_limit(request)
    user = db.users.find_one({'email': str(payload.email).lower()})
    valid = password_hasher.verify(payload.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, 'Email or password is incorrect.')
    audit(db, user['_id'], 'auth.login', user['_id'])
    return issue_token(db, user, request.app.state.settings)


@router.get('/auth/me')
def me(user=Depends(current_user)):
    return public(user)


@router.post('/auth/logout')
def logout(request: Request, user=Depends(current_user), db=Depends(get_db)):
    db.sessions.delete_one({'_id': request.state.session_id})
    audit(db, user['_id'], 'auth.logout', user['_id'])
    return {'message': 'Signed out successfully.'}


@router.get('/users/farmers')
def farmers(user=Depends(roles('paravet', 'admin')), db=Depends(get_db)):
    return [public(u) for u in db.users.find({'role': 'farmer', 'district': user['district']}, {'name': 1, 'email': 1})]
