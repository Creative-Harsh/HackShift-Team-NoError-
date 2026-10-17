from base64 import b64decode
from uuid import uuid4
import pytest
from mongomock.gridfs import enable_gridfs_integration

PNG=b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBWQAAAAASUVORK5CYII=')


@pytest.fixture(autouse=True)
def gridfs_for_mock():
    enable_gridfs_integration()


def upload(client, headers, kind='image', content=PNG, identifier=None):
    return client.post('/api/media',headers=headers,data={'kind':kind,'client_upload_id':identifier or str(uuid4())},
        files={'file':('evidence.png',content,'image/png')})


def test_private_attachment_round_trip_idempotency_and_role_scope(client,farmer,login,report_payload,other_farmer,db):
    key=str(uuid4())
    original=upload(client,farmer[0],identifier=key)
    assert original.status_code==201,original.text
    url=original.json()['url']
    assert upload(client,farmer[0],identifier=key).json()['id']==original.json()['id']
    assert db.media.count_documents({})==1
    assert upload(client,farmer[0],identifier=key,content=PNG+b'x').status_code==409
    assert client.get(url).status_code==401
    assert client.get(url,headers=other_farmer[0]).status_code==404
    vet=login('vet')[0]
    assert client.get(url,headers=vet).status_code==404
    case=client.post('/api/reports',headers=farmer[0],json={**report_payload,'image_url':url})
    assert case.status_code==201,case.text
    result=client.get(url,headers=vet)
    assert result.content==PNG and result.headers['content-type']=='image/png'
    assert result.headers['cache-control']=='no-store'
    lab=login('lab')[0]
    assert client.get(url,headers=lab).status_code==404
    db.lab_tests.insert_one({'_id':str(uuid4()),'district':'Pune','case_id':case.json()['id']})
    assert client.get(url,headers=lab).status_code==200


@pytest.mark.parametrize('role,kind',[('farmer','lab_report'),('vet','image'),('admin','voice_note'),('lab','image')])
def test_upload_role_boundary(client,login,role,kind):
    assert upload(client,login(role)[0],kind).status_code==403


def test_file_validation_and_media_kind_binding(client,farmer,report_payload):
    assert upload(client,farmer[0],content=b'<script>not an image</script>').status_code==422
    assert upload(client,farmer[0],content=b'').status_code==413
    assert upload(client,farmer[0],content=PNG+b'x'*(8*1024*1024)).status_code==413
    url=upload(client,farmer[0]).json()['url']
    assert client.post('/api/reports',headers=farmer[0],json={**report_payload,'voice_note_url':url}).status_code==422
    assert client.post('/api/reports',headers=farmer[0],json={**report_payload,'image_url':url+'?evil'}).status_code==422


def test_lab_pdf_is_private_until_attached(client,login):
    lab=login('lab')[0]
    pdf=b'%PDF-1.4\n% Synthetic test report\n%%EOF'
    response=upload(client,lab,'lab_report',pdf)
    assert response.status_code==201,response.text
    assert client.get(response.json()['url'],headers=lab).content==pdf
    assert client.get(response.json()['url'],headers=login('admin')[0]).status_code==404
