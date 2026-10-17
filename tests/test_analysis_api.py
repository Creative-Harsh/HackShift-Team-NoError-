"""Phase 2 integration checks exercise stored analyses, not a UI fixture."""
from copy import deepcopy


def test_report_persists_explained_preliminary_assessment(client, farmer, report_payload, db):
    response = client.post('/api/reports', json=report_payload, headers=farmer[0])
    assert response.status_code == 201, response.text
    case = response.json()
    assert case['triage']['suspected_disease'].lower().startswith(('possible', 'suspected'))
    assert case['confirmation_status'] == 'suspected'
    assert case['status'] == 'triage'
    assert sum(f['points'] for f in case['risk']['factors']) == case['risk']['score']
    assert 0 <= case['risk']['score'] <= 100
    assert [x['status'] for x in case['timeline']][:2] == ['reported', 'triage']
    stored = db.disease_cases.find_one({'_id': case['id']})
    assert stored['triage'] == case['triage']
    assert stored['initial_risk'] == stored['risk']
    risk = client.get('/api/risk/' + case['id'], headers=farmer[0])
    assert risk.status_code == 200 and risk.json() == case['risk']


def test_preview_does_not_write_a_case(client, farmer, report_payload, db):
    before = db.disease_cases.count_documents({})
    preview = client.post('/api/triage', json=report_payload, headers=farmer[0])
    assert preview.status_code == 200, preview.text
    assert preview.json()['saved'] is False
    assert preview.json()['risk']['factors']
    assert db.disease_cases.count_documents({}) == before


def test_risk_and_preview_honor_owner_permissions(client, farmer, other_farmer, report_payload):
    case = client.post('/api/reports', json=report_payload, headers=farmer[0]).json()
    assert client.get('/api/risk/' + case['id'], headers=other_farmer[0]).status_code == 404
    assert client.post('/api/triage', json=report_payload, headers=other_farmer[0]).status_code == 404


def test_evaluation_is_professional_and_labels_synthetic_limit(client, farmer, login):
    assert client.get('/api/evaluation', headers=farmer[0]).status_code == 403
    response = client.get('/api/evaluation', headers=login('admin')[0])
    assert response.status_code == 200
    assert 'Synthetic' in response.json()['limitations']
    assert response.json()['model_evaluation_available']
