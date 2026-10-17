from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app.database import new_id, public, utcnow

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash('invalid-password-timing-equalizer')
bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    if request.app.state.db is None:
        raise HTTPException(503, 'MongoDB is unavailable. Check backend configuration.')
    return request.app.state.db


def issue_token(db, user, settings):
    now = utcnow()
    expires = now + timedelta(minutes=settings.jwt_expire_minutes)
    jti = new_id()
    db.sessions.insert_one({'_id': jti, 'user_id': user['_id'], 'expires_at': expires, 'created_at': now})
    token = jwt.encode({'sub': user['_id'], 'jti': jti, 'iat': now, 'exp': expires,
                        'iss': 'pashuraksha', 'aud': 'pashuraksha-web'}, settings.jwt_secret, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'user': public(user)}


def current_user(request: Request, credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db=Depends(get_db)):
    error = HTTPException(401, 'Please sign in again.', headers={'WWW-Authenticate': 'Bearer'})
    if not credential:
        raise error
    try:
        claims = jwt.decode(credential.credentials, request.app.state.settings.jwt_secret, algorithms=['HS256'],
                            audience='pashuraksha-web', issuer='pashuraksha', options={'require': ['exp', 'sub', 'jti', 'iat']})
        session = db.sessions.find_one({'_id': claims['jti'], 'user_id': claims['sub'], 'expires_at': {'$gt': utcnow()}})
        user = db.users.find_one({'_id': claims['sub']})
        if not session or not user:
            raise error
        request.state.session_id = claims['jti']
        return user
    except jwt.PyJWTError:
        raise error


def roles(*allowed):
    def check(user=Depends(current_user)):
        if user['role'] not in allowed:
            raise HTTPException(403, 'This action is not permitted for your role.')
        return user
    return check


def scope(user, collection='animals'):
    if user['role'] == 'farmer':
        return {'owner_id': user['_id']}
    return {'district': user['district']}


def authorized_document(db, collection, identifier, user):
    query = {'_id': identifier, **scope(user, collection)}
    if user['role'] == 'lab':
        # Laboratory access is limited to cases/animals with a test in its district.
        tests = list(db.lab_tests.find({'district': user['district']}, {'case_id': 1}))
        case_ids = [t['case_id'] for t in tests]
        if collection == 'disease_cases':
            query['_id'] = {'$in': [identifier] if identifier in case_ids else []}
        elif collection == 'animals':
            animals = db.disease_cases.distinct('animal_id', {'_id': {'$in': case_ids}})
            query['_id'] = {'$in': [identifier] if identifier in animals else []}
    result = db[collection].find_one(query)
    if not result:
        raise HTTPException(404, 'Record not found or access unavailable.')
    if user['role'] == 'lab' and collection == 'animals':
        for history_key in ('disease_history', 'treatment_history', 'lab_history'):
            result[history_key] = [entry for entry in result.get(history_key, [])
                                   if entry.get('case_id') in case_ids and entry.get('district', user['district']) == user['district']]
    return result
