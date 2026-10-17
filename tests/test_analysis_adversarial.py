"""Adversarial checks for the preliminary-assessment boundary and provenance."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

import pytest


@pytest.mark.parametrize("field,value", [
    ("risk", {"score": 0, "level": "LOW"}),
    ("triage", {"suspected_disease": "Confirmed disease", "probability": 1}),
    ("status", "confirmed"),
    ("confirmation_status", "confirmed"),
])
def test_report_cannot_inject_assessment_or_confirmation(client, farmer, report_payload, db, field, value):
    report_payload[field] = value
    before = db.disease_cases.count_documents({})
    response = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert response.status_code == 422, response.text
    assert db.disease_cases.count_documents({}) == before


def test_preview_preserves_ehr_audit_and_database_state(client, farmer, report_payload, db):
    original_animal = deepcopy(db.animals.find_one({"_id": report_payload["animal_id"]}))
    collections = ("disease_cases", "audit_logs", "notifications", "outbreak_clusters", "lab_tests")
    before = {name: db[name].count_documents({}) for name in collections}
    response = client.post("/api/triage", json=report_payload, headers=farmer[0])
    assert response.status_code == 200, response.text
    assert response.json()["saved"] is False
    assert db.animals.find_one({"_id": report_payload["animal_id"]}) == original_animal
    assert {name: db[name].count_documents({}) for name in collections} == before


def test_analysis_endpoints_protect_district_and_lab_scope(client, farmer, login, report_payload, db):
    case_response = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert case_response.status_code == 201, case_response.text
    case_id = case_response.json()["id"]
    lab_headers, _ = login("lab")
    assert client.post("/api/triage", json=report_payload, headers=lab_headers).status_code == 403
    assert client.get(f"/api/risk/{case_id}", headers=lab_headers).status_code == 404
    db.lab_tests.insert_one({"_id": str(uuid4()), "case_id": case_id, "district": "Pune"})
    allowed = client.get(f"/api/risk/{case_id}", headers=lab_headers)
    assert allowed.status_code == 200
    assert allowed.json() == case_response.json()["risk"]
    assert client.get("/api/evaluation", headers=lab_headers).status_code == 403

    db.animals.update_one({"_id": report_payload["animal_id"]}, {"$set": {"district": "Other District"}})
    db.disease_cases.update_one({"_id": case_id}, {"$set": {"district": "Other District"}})
    for role in ("paravet", "vet", "admin"):
        headers, _ = login(role)
        assert client.post("/api/triage", json=report_payload, headers=headers).status_code == 404
        assert client.get(f"/api/risk/{case_id}", headers=headers).status_code == 404


def test_retry_keeps_original_assessment_after_ehr_changes(client, farmer, report_payload, db, monkeypatch):
    from app.services import reports

    initial = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert initial.status_code == 201, initial.text
    db.animals.update_one({"_id": report_payload["animal_id"]}, {"$set": {"age_months": 480}})

    def must_not_reassess(*args, **kwargs):
        raise AssertionError("A sync retry must return its stored assessment, not recalculate")

    monkeypatch.setattr(reports, "analyze_observation", must_not_reassess)
    retry = client.post("/api/reports", json=report_payload, headers=farmer[0])
    assert retry.status_code == 200, retry.text
    for field in ("id", "triage", "risk", "initial_risk", "assessed_at", "timeline"):
        assert retry.json()[field] == initial.json()[field]


@pytest.mark.parametrize("artifact_bytes", [None, b"\x80\x04\x95", b"broken"])
def test_missing_or_corrupt_classifier_keeps_report_path_working(client, farmer, report_payload, monkeypatch, tmp_path, artifact_bytes):
    import sklearn
    from app.triage import classifier
    from app.triage.features import FEATURE_NAMES, FEATURE_VERSION

    monkeypatch.setattr(classifier, "ARTIFACT_DIR", tmp_path)
    if artifact_bytes is not None:
        (tmp_path / "metadata.json").write_text(json.dumps({
            "feature_names": list(FEATURE_NAMES), "feature_version": FEATURE_VERSION,
            "sklearn_version": sklearn.__version__, "model_version": "corrupted-test-artifact",
            "model_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        }), encoding="utf-8")
        (tmp_path / "model.joblib").write_bytes(artifact_bytes)
    classifier.load_model.cache_clear()
    try:
        response = client.post("/api/reports", json=report_payload, headers=farmer[0])
        assert response.status_code == 201, response.text
        case = response.json()
        assert case["confirmation_status"] == "suspected"
        assert case["triage"]["probability"] is None
        assert case["triage"]["probability_kind"] == "unavailable_rules_only"
        assert "rules" in case["triage"]["model_source"].lower()
        assert case["triage"]["suspected_disease"] == "Possible Lumpy Skin Disease"
        assert sum(factor["points"] for factor in case["risk"]["factors"]) == case["risk"]["score"]
        assert next(factor["points"] for factor in case["risk"]["factors"] if factor["key"] == "disease_probability") == 0
    finally:
        classifier.load_model.cache_clear()


def test_incomplete_classifier_metadata_degrades_to_rules(monkeypatch, tmp_path):
    from app.triage import assess, classifier

    source = classifier.ARTIFACT_DIR
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    metadata.pop("model_version")
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "model.joblib").write_bytes((source / "model.joblib").read_bytes())
    monkeypatch.setattr(classifier, "ARTIFACT_DIR", tmp_path)
    classifier.load_model.cache_clear()
    try:
        report = {"symptoms": ["fever", "skin_lesions", "swelling"], "vaccination_status": "unknown"}
        animal = {"species": "cattle", "age_months": 36}
        assessment = assess(report, animal, datetime(2026, 9, 12, tzinfo=timezone.utc))
        assert assessment["probability"] is None
        assert assessment["probability_kind"] == "unavailable_rules_only"
    finally:
        classifier.load_model.cache_clear()
