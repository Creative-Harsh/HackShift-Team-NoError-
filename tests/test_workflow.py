from uuid import uuid4
import pytest


def op(case, **fields):
    return {'operation_id': str(uuid4()), 'expected_version': case['version'], **fields}


def new_case(client, farmer, report_payload):
    response = client.post('/api/reports', headers=farmer[0], json=report_payload)
    assert response.status_code == 201, response.text
    return response.json()


def advance(client, headers, case, action, method='put', **fields):
    response = getattr(client, method)(f"/api/cases/{case['id']}/{action}", headers=headers, json=op(case, **fields))
    assert response.status_code == 200, response.text
    return response.json()


def sample_case(client, farmer, report_payload, login):
    case = new_case(client, farmer, report_payload)
    vet = login('vet')[0]
    case = advance(client, vet, case, 'assign-vet', 'post')
    case = advance(client, vet, case, 'vet-review', diagnosis='Suspected LSD; examination recorded.', recommendations='Isolate and monitor pending laboratory investigation.')
    case = advance(client, vet, case, 'request-lab', 'post', test_type='LSD PCR', disease_code='lsd', notes='Lesion swab requested.')
    return case, vet


@pytest.mark.parametrize('result,expected', [('positive', 'confirmed'), ('negative', 'rejected'), ('inconclusive', 'inconclusive')])
def test_complete_lab_and_control_workflow(client, farmer, report_payload, login, db, result, expected):
    case, vet = sample_case(client, farmer, report_payload, login)
    lab = login('lab')[0]
    tests = client.get('/api/lab/requests', headers=lab).json()
    test = tests[0]
    assert test['case_version'] == case['version']
    for status in ('received', 'testing', result):
        payload = op(case, status=status, result_notes='Recorded laboratory findings.')
        if status == 'positive':
            payload['confirmed_disease'] = 'lsd'
        response = client.put(f"/api/lab/tests/{test['id']}", headers=lab, json=payload)
        assert response.status_code == 200, response.text
        case = response.json()['case']
    assert case['status'] == case['confirmation_status'] == expected
    assert client.put(f"/api/lab/tests/{test['id']}", headers=lab, json=op(case, status='negative', result_notes='Overwrite')).status_code == 409
    animal = db.animals.find_one({'_id': case['animal_id']})
    assert animal['lab_history'][0]['status'] == result
    case = advance(client, vet, case, 'status', status='treatment', note='Veterinarian recorded isolation and monitoring control action.')
    case = advance(client, vet, case, 'status', status='closed', note='Follow-up completed and episode closed by veterinarian.')
    assert case['status'] == 'closed'
    assert db.animals.find_one({'_id': case['animal_id']})['health_status'] == 'healthy'
    assert db.notifications.count_documents({'case_id': case['id']}) > 0


def test_permissions_versions_and_evidence_guards(client, farmer, report_payload, login):
    case = new_case(client, farmer, report_payload)
    assert 'animal_snapshot' not in case
    for role in ('farmer', 'paravet', 'lab'):
        assert client.post(f"/api/cases/{case['id']}/assign-vet", headers=login(role)[0], json=op(case)).status_code == 403
    vet = login('vet')[0]
    command = op(case)
    first = client.post(f"/api/cases/{case['id']}/assign-vet", headers=vet, json=command).json()
    retry = client.post(f"/api/cases/{case['id']}/assign-vet", headers=vet, json=command).json()
    assert first['version'] == retry['version']
    assert first['timeline'] == retry['timeline']
    assert 'workflow_operations' not in first
    stale = client.put(f"/api/cases/{case['id']}/vet-review", headers=vet, json=op(case, diagnosis='review', recommendations='monitor'))
    assert stale.status_code == 409
    assert client.put(f"/api/cases/{case['id']}/status", headers=vet, json=op(first, status='closed', note='Close early')).status_code == 409
    assert client.get('/api/vet/queue', headers=farmer[0]).status_code == 403


def test_lab_requires_receipt_testing_and_matching_target(client, farmer, report_payload, login):
    case, vet = sample_case(client, farmer, report_payload, login)
    lab = login('lab')[0]
    test = case['lab_tests'][0]
    path = f"/api/lab/tests/{test['id']}"
    assert client.put(path, headers=lab, json=op(case, status='positive', result_notes='Positive PCR', confirmed_disease='lsd')).status_code == 409
    assert client.put(f"/api/cases/{case['id']}/status", headers=vet, json=op(case, status='treatment', note='Bypass pending lab')).status_code == 409
    for status in ('received', 'testing'):
        case = client.put(path, headers=lab, json=op(case, status=status)).json()['case']
    assert client.put(path, headers=lab, json=op(case, status='positive', result_notes='Positive', confirmed_disease='fmd')).status_code == 422
    assert client.put(path, headers=vet, json=op(case, status='negative', result_notes='Negative')).status_code == 403


def test_interrupted_projection_is_repaired_without_duplicate_sample(client, farmer, report_payload, login, db, monkeypatch):
    case = new_case(client, farmer, report_payload)
    vet = login('vet')[0]
    case = advance(client, vet, case, 'assign-vet', 'post')
    case = advance(client, vet, case, 'vet-review', diagnosis='Suspected LSD', recommendations='Isolate and monitor')
    payload = op(case, test_type='LSD PCR')
    path = f"/api/cases/{case['id']}/request-lab"
    with monkeypatch.context() as patch:
        patch.setattr(db.lab_tests, 'replace_one', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('simulated interrupted projection')))
        with pytest.raises(RuntimeError):
            client.post(path, headers=vet, json=payload)
    response = client.post(path, headers=vet, json=payload)
    assert response.status_code == 200, response.text
    assert len(response.json()['lab_tests']) == db.lab_tests.count_documents({}) == 1
    assert db.disease_cases.find_one({'_id': case['id']})['projection_pending'] is False


def test_admin_statistics_and_explicit_outbreak_confirmation(client, login, db):
    admin = login('admin')[0]
    replay = client.post('/api/demo/replay', headers=admin, json={'steps': 11}).json()
    cluster = replay['clusters'][0]
    assert cluster['status'] != 'confirmed_outbreak'
    path = f"/api/outbreaks/{cluster['id']}/confirm"
    assert client.post(path, headers=admin, json={'evidence_test_ids': ['fake'], 'note': 'Investigated cluster evidence'}).status_code == 422
    case = client.get(f"/api/cases/{cluster['case_ids'][0]}", headers=admin).json()
    vet = login('vet')[0]
    case = advance(client, vet, case, 'assign-vet', 'post')
    case = advance(client, vet, case, 'vet-review', diagnosis='Possible LSD after examination', recommendations='Isolate and monitor')
    case = advance(client, vet, case, 'request-lab', 'post', test_type='LSD PCR')
    test_id = case['lab_tests'][0]['id']
    lab = login('lab')[0]
    for status in ('received', 'testing', 'positive'):
        payload = op(case, status=status, result_notes='PCR positive' if status == 'positive' else '')
        if status == 'positive':
            payload['confirmed_disease'] = 'lsd'
        case = client.put(f'/api/lab/tests/{test_id}', headers=lab, json=payload).json()['case']
    body = {'evidence_test_ids': [test_id], 'note': 'District officer reviewed laboratory evidence and field investigation.'}
    assert client.post(path, headers=lab, json=body).status_code == 403
    result = client.post(path, headers=admin, json=body)
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'confirmed_outbreak'
    stats = client.get('/api/admin/dashboard', headers=admin).json()
    assert stats['kpis']['total_animals'] == db.animals.count_documents({'district': 'Pune'})
    assert stats['kpis']['confirmed_outbreaks'] == 1
    assert stats['operational']['assigned_case_count'] == 1
    assert client.get('/api/admin/dashboard', headers=login('farmer')[0]).status_code == 403
