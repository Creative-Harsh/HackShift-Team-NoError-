from copy import deepcopy
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from app.assistant.provider import sanitized_text
from app.assistant.schemas import IntentExtraction
from app.assistant.service import CATALOG
from app.routes.assistant import _events


@pytest.fixture(autouse=True)
def clear_assistant_limit():
    _events.clear()


def snapshot(db):
    return {name: list(db[name].find({})) for name in db.list_collection_names()}


def test_assistant_requires_auth_and_does_not_mutate(client, farmer, db):
    assert client.post('/api/assistant/message', json={'text': 'report'}).status_code == 401
    headers, _ = farmer
    before = snapshot(db)
    response = client.post('/api/assistant/message', headers=headers, json={'text': 'report kaise banau', 'context': {'page': 'home', 'targets': ['nav-report']}})
    assert response.status_code == 200
    assert response.json()['target'] == 'nav-report'
    assert snapshot(db) == before
    assert client.get('/api/assistant/capabilities', headers=headers).json()['record_mutation_tools'] == []


@pytest.mark.parametrize('text,target', [('Photo kaha upload karu?', 'animal-photo'), ('Animal kaise add karu?','register-animal'), ('मेरी रिपोर्ट कहाँ है?', 'nav-cases')])
def test_help_languages(client, farmer, text, target):
    headers, _ = farmer
    r=client.post('/api/assistant/message', headers=headers, json={'text':text, 'context':{'page':'home','targets':[]}})
    assert r.status_code == 200
    assert r.json()['target'] == target


def test_consent_role_and_injection_boundaries(client, farmer):
    headers,_=farmer
    assert client.post('/api/assistant/message',headers=headers,json={'text':'report'}).json()['message_key']=='consent'
    denied=client.post('/api/assistant/message',headers=headers,json={'text':'sample request','context':{'page':'home','targets':[]}}).json()
    assert denied['target'] is None and denied['message_key']=='denied'
    for target in ['body', 'button[onclick]', 'admin-confirmation', '<script>submit()</script>']:
        assert client.post('/api/assistant/message',headers=headers,json={'text':'help','context':{'page':'home','targets':[target]}}).status_code==422
    assert client.post('/api/assistant/message',headers=headers,json={'text':'help','role':'admin'}).status_code==422
    with pytest.raises(ValidationError):
        IntentExtraction.model_validate({'intent':'click','evidence':'click'})
    with pytest.raises(ValidationError):
        IntentExtraction.model_validate({'intent':'report','evidence':'report','spokenText':'Take medicine'})


def test_current_status_is_authorized_and_real(client, farmer, report_payload, other_farmer):
    headers,_=farmer
    case=client.post('/api/reports',headers=headers,json=report_payload).json()
    payload={'text':'my report status','context':{'page':'case_detail','targets':['case-status'],'case_id':case['id']}}
    r=client.post('/api/assistant/message',headers=headers,json=payload)
    assert r.json()['case_status']==case['status']
    assert client.post('/api/assistant/message',headers=other_farmer[0],json=payload).status_code==404
    payload['context']['page']='home'
    assert client.post('/api/assistant/message',headers=headers,json=payload).status_code==422


def test_partial_concern_uses_existing_rules_without_defaults_or_saving(client, farmer, owned_animal, db):
    headers,_=farmer
    before=deepcopy(snapshot(db))
    r=client.post('/api/assistant/concern',headers=headers,json={'animal_id':owned_animal['id'],'observations':{'symptoms':{'fever':True,'cough':False},'appetite':'none'},'verified':True})
    assert r.status_code==200, r.text
    body=r.json()
    assert body['message_key']=='urgent' and body['severity']=='high'
    assert body['risk_score'] is None and body['saved'] is False
    assert any('APPETITE_ALERT' in rule for rule in body['triggered_rules'])
    assert 'temperature_c' in body['missing_information'] and 'cough' not in body['missing_information']
    assert snapshot(db)==before


def test_missing_symptoms_are_not_normal_and_lab_cannot_assess(client, farmer, owned_animal, login):
    headers,_=farmer
    payload={'animal_id':owned_animal['id'],'observations':{'symptoms':{}},'verified':True}
    result=client.post('/api/assistant/concern',headers=headers,json=payload).json()
    assert result['message_key']=='insufficient' and result['severity'] is None
    assert client.post('/api/assistant/concern',headers=login('lab')[0],json=payload).status_code==403
    payload['verified']=False
    assert client.post('/api/assistant/concern',headers=headers,json=payload).status_code==422


def test_provider_requires_opt_in_and_failure_is_contained(client, farmer):
    from pydantic import SecretStr
    settings=client.app.state.settings
    headers,_=farmer
    with patch.object(settings,'gemini_api_key',SecretStr('test-placeholder')),patch.object(settings,'gemini_model','test-model'),patch('app.assistant.service.GeminiIntentProvider.classify',side_effect=ValueError('bad output')) as provider:
        data={'text':'xyz unrecognized','context':{'page':'home','targets':[]}}
        assert client.post('/api/assistant/message',headers=headers,json=data).status_code==200
        provider.assert_not_called()
        data['external_consent']=True
        result=client.post('/api/assistant/message',headers=headers,json=data).json()
        assert result['source']=='fallback' and result['target'] is None


def test_catalog_and_provider_data_minimization():
    assert len(CATALOG['targets'])==len(set(CATALOG['targets']))
    assert all(e['target'] in CATALOG['targets'] for e in CATALOG['intents'])
    value=sanitized_text('My email a@example.org, tag 261280000001 and token eyJabc.def.ghi https://private.invalid')
    for sensitive in ['a@example.org','261280000001','eyJabc.def.ghi','private.invalid']:
        assert sensitive not in value


@pytest.mark.parametrize('value', [False, 1, 'true', None])
def test_verification_is_an_explicit_boolean(value):
    from app.assistant.schemas import ConcernInput
    with pytest.raises(ValidationError):
        ConcernInput.model_validate({'animal_id':'test', 'observations':{'symptoms':{}}, 'verified':value})


def test_provider_rest_contract_and_rejection_of_untrusted_prose():
    import httpx
    from pydantic import SecretStr
    from types import SimpleNamespace
    from app.assistant.provider import GeminiIntentProvider
    settings=SimpleNamespace(gemini_api_key=SecretStr('test-key'),gemini_model='test-model')
    provider=GeminiIntentProvider(settings)
    request=httpx.Request('POST','https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent')
    good={'candidates':[{'content':{'parts':[{'text':'{"intent":"report","evidence":"report"}'}]}}]}
    with patch('app.assistant.provider.httpx.Client') as client:
        post=client.return_value.__enter__.return_value.post
        post.return_value=httpx.Response(200,json=good,request=request)
        assert provider.classify('help me report').intent=='report'
        call=post.call_args
        assert call.args[0]==str(request.url)
        body=call.kwargs['json']
        assert 'tools' not in body and 'systemInstruction' not in body
        assert body['generationConfig']['responseMimeType']=='application/json'
        assert 'target' not in body['generationConfig']['responseJsonSchema']['properties']
        for content in ['{"intent":"report","evidence":"unrelated"}', '{"intent":"report","evidence":"report","spokenText":"medicine"}', '{"intent":"click","evidence":"report"}']:
            post.return_value=httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':content}]}}]},request=request)
            with pytest.raises(ValueError):provider.classify('help me report')
        post.return_value=httpx.Response(200,json={'candidates':[None]},request=request)
        with pytest.raises(ValueError):provider.classify('help me report')


def test_concern_ownership_and_strict_observations(client, farmer, owned_animal, other_farmer):
    payload={'animal_id':owned_animal['id'],'observations':{'symptoms':{'fever':True}},'verified':True}
    assert client.post('/api/assistant/concern',headers=other_farmer[0],json=payload).status_code==404
    for symptoms in [{'invented':True},{'fever':'true'},{'fever':1}]:
        payload['observations']['symptoms']=symptoms
        assert client.post('/api/assistant/concern',headers=farmer[0],json=payload).status_code==422
