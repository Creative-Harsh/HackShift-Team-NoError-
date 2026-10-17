from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pymongo.errors import AutoReconnect


def test_structured_report_persists_and_is_in_ehr(client, farmer, report_payload, owned_animal, db):
    headers, _ = farmer
    response = client.post("/api/reports", json=report_payload, headers=headers)
    assert response.status_code == 201, response.text
    case = response.json()
    assert case["animal_id"] == owned_animal["id"]
    assert case["reporter_id"] == farmer[1]["id"]
    assert set(case["report"]["symptoms"]) == set(report_payload["symptoms"])
    assert case["location"] == report_payload["location"]
    assert case["confirmation_status"] != "confirmed"
    assert "triage" in case and "risk" in case
    assert db.disease_cases.find_one({"_id": case["id"]}) is not None
    assert client.get(f"/api/cases/{case['id']}", headers=headers).status_code == 200
    history = client.get(f"/api/animals/{owned_animal['id']}/history", headers=headers).json()
    assert case["id"] in {entry["id"] for entry in history["cases"]}


def test_report_retry_returns_same_case_without_duplicate(client, farmer, report_payload, db):
    headers, _ = farmer
    first = client.post("/api/reports", json=report_payload, headers=headers)
    assert first.status_code == 201, first.text
    before = db.disease_cases.count_documents({})
    second = client.post("/api/reports", json=report_payload, headers=headers)
    assert second.status_code in (200, 201), second.text
    assert second.json()["id"] == first.json()["id"]
    assert db.disease_cases.count_documents({}) == before


def test_conflicting_uuid_reuse_rejected(client, farmer, report_payload, db):
    first = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert first.status_code == 201
    changed = deepcopy(report_payload)
    changed["mortality_count"] = 1
    response = client.post("/api/reports", json=changed, headers=farmer[0])
    assert response.status_code == 409
    stored = db.disease_cases.find_one({"_id": first.json()["id"]})
    assert stored["report"]["mortality_count"] == 0


@pytest.mark.parametrize("role", ["lab", "vet", "admin"])
def test_non_reporting_roles_cannot_submit_reports(client, login, report_payload, role):
    headers, _ = login(role)
    response = client.post("/api/reports", json=report_payload, headers=headers)
    assert response.status_code == 403


def test_farmer_cannot_report_or_read_another_owners_case(client, farmer, other_farmer, report_payload):
    first = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert first.status_code == 201
    case_id = first.json()["id"]
    assert client.post("/api/reports", json=report_payload, headers=other_farmer[0]).status_code in (403, 404)
    assert client.get(f"/api/cases/{case_id}", headers=other_farmer[0]).status_code in (403, 404)
    assert case_id not in {case["id"] for case in client.get("/api/cases", headers=other_farmer[0]).json()}


def test_paravet_can_report_district_animal(client, login, report_payload):
    headers, user = login("paravet")
    response = client.post("/api/reports", json=report_payload, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["reporter_id"] == user["id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("client_report_id", "not-a-uuid"),
        ("symptoms", ["made_up_disease"]),
        ("milk_drop_percent", 101),
        ("milk_drop_percent", -1),
        ("mortality_count", -1),
        ("duration_hours", -1),
        ("duration_hours", 2161),
        ("temperature_c", 100),
        ("location", {"type": "Point", "coordinates": [73, 91]}),
        ("reported_at", (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()),
    ],
)
def test_invalid_structured_report_rejected(client, farmer, report_payload, field, value):
    report_payload[field] = value
    response = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("failing_collection", ["animals", "audit_logs"])
def test_report_retry_reconciles_partial_database_write(client, farmer, report_payload, db, monkeypatch, failing_collection):
    collection = db[failing_collection]
    update_one = collection.update_one
    failure_pending = True

    def fail_first_update(*args, **kwargs):
        nonlocal failure_pending
        if failure_pending:
            failure_pending = False
            raise AutoReconnect("Simulated connection interruption after case write")
        return update_one(*args, **kwargs)

    monkeypatch.setattr(collection, "update_one", fail_first_update)
    interrupted = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert interrupted.status_code == 503, interrupted.text
    stored = db.disease_cases.find_one({"client_report_id": report_payload["client_report_id"]})
    assert stored is not None
    for _ in range(2):
        retry = client.post("/api/reports", json=report_payload, headers=farmer[0])
        assert retry.status_code == 200, retry.text
        assert retry.json()["id"] == stored["_id"]
    assert db.disease_cases.count_documents({"client_report_id": report_payload["client_report_id"]}) == 1
    assert db.animals.find_one({"_id": report_payload["animal_id"]})["health_status"] == "under_observation"
    assert db.audit_logs.count_documents({"action": "report.create", "resource_id": stored["_id"]}) == 1


def test_retry_of_closed_case_does_not_reopen_animal_episode(client, farmer, report_payload, db):
    first = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert first.status_code == 201
    db.disease_cases.update_one({"_id": first.json()["id"]}, {"$set": {"status": "closed"}})
    db.animals.update_one({"_id": report_payload["animal_id"]}, {"$set": {"health_status": "healthy"}})
    retry = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert retry.status_code == 200
    assert retry.json()["status"] == "closed"
    assert db.animals.find_one({"_id": report_payload["animal_id"]})["health_status"] == "healthy"
