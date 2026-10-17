"""Private MongoDB GridFS object storage. No public attachment URLs or external service claim."""
import hashlib
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from gridfs import GridFS
from gridfs.errors import NoFile
from pymongo.errors import DuplicateKeyError
from app.auth import authorized_document, current_user, get_db, scope
from app.database import new_id, utcnow

router = APIRouter(tags=['Private attachments'])
LIMIT = 8 * 1024 * 1024


def detected_type(data):
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if data.startswith(b'%PDF-'): return 'application/pdf'
    if data.startswith(b'OggS'): return 'audio/ogg'
    if data.startswith(b'RIFF') and data[8:12] == b'WAVE': return 'audio/wav'
    if data.startswith(b'ID3') or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224): return 'audio/mpeg'
    if data.startswith(b'\x1aE\xdf\xa3'): return 'audio/webm'
    return None


@router.post('/media', status_code=201)
async def upload(request: Request, file: Annotated[UploadFile, File()],
    kind: Annotated[Literal['image', 'voice_note', 'lab_report'], Form()],
    client_upload_id: Annotated[UUID, Form()], user=Depends(current_user), db=Depends(get_db)):
    if (kind == 'lab_report' and user['role'] != 'lab') or (kind != 'lab_report' and user['role'] not in ('farmer', 'paravet')):
        raise HTTPException(403, 'Your role cannot upload this attachment type.')
    data = await file.read(LIMIT + 1)
    await file.close()
    if not data or len(data) > LIMIT:
        raise HTTPException(413, 'Choose a nonempty attachment no larger than 8 MB.')
    mime = detected_type(data)
    allowed = {'image': {'image/jpeg', 'image/png'}, 'voice_note': {'audio/ogg', 'audio/wav', 'audio/mpeg', 'audio/webm'},
               'lab_report': {'application/pdf', 'image/jpeg', 'image/png'}}
    if mime not in allowed[kind]:
        raise HTTPException(422, 'File contents do not match a supported attachment format.')
    digest = hashlib.sha256(data).hexdigest()
    identity = {'uploaded_by': user['_id'], 'client_upload_id': str(client_upload_id)}
    existing = db.media.find_one(identity)
    if existing:
        if existing['sha256'] != digest or existing['kind'] != kind:
            raise HTTPException(409, 'Upload ID was already used for a different attachment.')
        return {'id': existing['_id'], 'url': '/api/media/' + existing['_id'], 'kind': kind, 'mime_type': mime, 'size': existing['size']}
    identifier = new_id()
    storage = GridFS(db)
    object_id = storage.put(data, content_type=mime, filename=identifier)
    item = {'_id': identifier, **identity, 'kind': kind, 'mime_type': mime, 'size': len(data), 'sha256': digest,
            'object_id': object_id, 'district': user['district'], 'created_at': utcnow()}
    try:
        db.media.insert_one(item)
    except DuplicateKeyError:
        storage.delete(object_id)
        original = db.media.find_one(identity)
        if not original or original['sha256'] != digest or original['kind'] != kind:
            raise HTTPException(409, 'Conflicting upload ID.')
        identifier = original['_id']
    except Exception:
        storage.delete(object_id)
        raise
    return {'id': identifier, 'url': '/api/media/' + identifier, 'kind': kind, 'mime_type': mime, 'size': len(data)}


@router.get('/media/{media_id}')
def download(media_id: str, user=Depends(current_user), db=Depends(get_db)):
    media = db.media.find_one({'_id': media_id})
    if not media:
        raise HTTPException(404, 'Attachment not found.')
    if media['uploaded_by'] != user['_id']:
        url = '/api/media/' + media_id
        query = {**scope(user, 'disease_cases'), '$or': [{'report.image_url': url}, {'report.voice_note_url': url}, {'lab_tests.attachment_url': url}]}
        if user['role'] == 'lab':
            query['_id'] = {'$in': db.lab_tests.distinct('case_id', {'district': user['district']})}
        case = db.disease_cases.find_one(query)
        if not case:
            raise HTTPException(404, 'Attachment not found.')
        authorized_document(db, 'disease_cases', case['_id'], user)
    try:
        data = GridFS(db).get(media['object_id']).read()
    except NoFile:
        raise HTTPException(404, 'Stored attachment is unavailable.')
    return Response(data, media_type=media['mime_type'], headers={
        'Content-Disposition': f'attachment; filename="{media_id}"', 'Cache-Control': 'no-store',
        'Content-Security-Policy': "default-src 'none'; sandbox"})
