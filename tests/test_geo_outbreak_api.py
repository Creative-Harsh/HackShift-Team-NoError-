"""Phase 3 API isolation, query contracts and calculated demo progression."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest

from app.database import utcnow


def add_case(db, animal, *, disease="lsd", species="cattle", village="Shirgaon", district="Pune", hours_ago=1):
    now = utcnow()
    identifier = str(uuid4())
    case = {
        "_id": identifier, "animal_id": animal["id"], "animal_name": animal["name"],
        "pashu_id": animal["pashu_id"], "species": species, "owner_id": animal["owner_id"],
        "owner_name": animal["owner_name"], "reporter_id": animal["owner_id"],
        "client_report_id": str(uuid4()), "district": district, "village": village,
        "location": deepcopy(animal["location"]), "reported_at": now - timedelta(hours=hours_ago),
        "created_at": now, "updated_at": now, "status": "triage", "confirmation_status": "suspected",
        "triage": {"disease_code": disease, "suspected_disease": "Possible " + disease},
        "risk": {"score": 60, "level": "HIGH", "factors": [], "version": "test-fixture"},
        "report": {"symptoms": ["fever", "skin_lesions"], "vaccination_status": "overdue"},
        "timeline": [], "assigned_vet_id": None,
    }
    db.disease_cases.insert_one(case)
    return case


@pytest.mark.parametrize("role", ["farmer", "lab"])
def test_detailed_surveillance_is_restricted_to_professionals(client, login, role):
    headers, _ = login(role)
    for path in ("/api/outbreaks/map", "/api/outbreaks"):
        assert client.get(path, headers=headers).status_code == 403
    assert client.post("/api/outbreaks/recalculate", headers=headers).status_code == 403


def test_map_filters_combine_and_cannot_escape_district(client, login, db, owned_animal):
    wanted = add_case(db, owned_animal)
    add_case(db, owned_animal, disease="fmd")
    add_case(db, owned_animal, species="buffalo")
    add_case(db, owned_animal, village="Somatane")
    foreign = add_case(db, owned_animal, district="Other District")
    stale = add_case(db, owned_animal, hours_ago=240)
    headers, _ = login("admin")
    response = client.get("/api/outbreaks/map", headers=headers, params={
        "days": 3, "disease": "lsd", "species": "cattle", "village": "Shirgaon", "district": "Pune",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert {"cases", "clusters", "total_cases", "truncated", "config", "generated_at"} <= result.keys()
    assert {case["id"] for case in result["cases"]} == {wanted["_id"]}
    assert result["total_cases"] == 1
    assert result["truncated"] is False
    default = client.get("/api/outbreaks/map", headers=headers).json()
    assert not {foreign["_id"], stale["_id"]} & {case["id"] for case in default["cases"]}
    outside = client.get("/api/outbreaks/map", headers=headers, params={"district": "Other District"})
    assert outside.status_code in (200, 403)
    if outside.status_code == 200:
        assert outside.json()["cases"] == []
        assert outside.json()["clusters"] == []


def test_field_worker_can_view_but_cannot_recalculate_or_replay(client, login):
    headers, _ = login("paravet")
    assert client.get("/api/outbreaks/map", headers=headers).status_code == 200
    assert client.post("/api/outbreaks/recalculate", headers=headers).status_code == 403
    assert client.post("/api/demo/replay", headers=headers, json={"steps": 1}).status_code == 403
    assert client.get("/api/demo/status", headers=headers).status_code == 403


def test_cluster_list_and_detail_cannot_expose_another_district(client, login, db):
    identifier = str(uuid4())
    db.outbreak_clusters.insert_one({"_id": identifier, "district": "Other District", "active": True,
                                    "case_ids": [], "score": 95, "status": "suspected_outbreak"})
    headers, _ = login("admin")
    listing = client.get("/api/outbreaks", headers=headers)
    assert listing.status_code == 200, listing.text
    assert identifier not in {cluster["id"] for cluster in listing.json()}
    assert client.get(f"/api/outbreaks/{identifier}", headers=headers).status_code == 404


@pytest.mark.parametrize("parameters", [
    {"longitude": 181, "latitude": 18},
    {"longitude": 73, "latitude": 91},
    {"longitude": 73, "latitude": 18, "radius_km": 0},
    {"longitude": 73, "latitude": 18, "radius_km": -1},
    {"longitude": 73, "latitude": 18, "days": 0},
])
def test_nearby_query_rejects_invalid_geometry_and_window(client, farmer, parameters):
    response = client.get("/api/cases/nearby", headers=farmer[0], params=parameters)
    assert response.status_code == 422, response.text


def test_nearby_builds_real_mongo_near_with_meter_units_and_time_window(client, login, db, owned_animal, monkeypatch):
    case = add_case(db, owned_animal)
    find = db.disease_cases.find
    queries = []

    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    def capture_geo_query(query=None, *args, **kwargs):
        if any("$near" in node for node in walk(query)):
            queries.append(deepcopy(query))
            # mongomock cannot execute $near. Actual distances have a separate real-Mongo test.
            return find({"_id": case["_id"]})
        return find(query, *args, **kwargs)

    monkeypatch.setattr(db.disease_cases, "find", capture_geo_query)
    before = utcnow()
    response = client.get("/api/cases/nearby", headers=login("vet")[0], params={
        "longitude": 73.685, "latitude": 18.725, "radius_km": 2.5, "days": 7, "disease": "lsd",
    })
    assert response.status_code == 200, response.text
    assert queries, "Nearby API must issue a real Mongo $near query"
    nodes = list(walk(queries[-1]))
    near = next(node["$near"] for node in nodes if "$near" in node)
    assert near["$geometry"] == {"type": "Point", "coordinates": [73.685, 18.725]}
    assert near["$maxDistance"] == 2500
    assert any(node.get("district") == "Pune" for node in nodes)
    assert any(node.get("triage.disease_code") == "lsd" for node in nodes)
    period = next(node["reported_at"] for node in nodes if "reported_at" in node)
    assert before - timedelta(days=7, seconds=2) <= period["$gte"] <= utcnow() - timedelta(days=7) + timedelta(seconds=2)
    assert "$lte" in period, "Future reports must not contribute to current nearby activity"


def test_demo_progression_uses_persisted_cases_and_preserves_confirmation(client, login, db):
    headers, _ = login("admin")
    status = client.get("/api/demo/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["enabled"] is True
    assert status.json()["completed"] == 0
    first = client.post("/api/demo/replay", headers=headers, json={"steps": 1})
    assert first.status_code == 200, first.text
    assert first.json()["completed"] == 1
    assert first.json()["clusters"] == []
    first_id = first.json()["new_case_ids"][0]
    initial_case = deepcopy(db.disease_cases.find_one({"_id": first_id}))
    for _ in range(6):
        result = client.post("/api/demo/replay", headers=headers, json={"steps": 1})
        assert result.status_code == 200, result.text
    assert result.json()["completed"] == 7
    clusters = client.get("/api/outbreaks", headers=headers).json()
    assert clusters, "Seven concentrated similar demo reports must create a calculated cluster"
    cluster = clusters[0]
    assert len(set(cluster["case_ids"])) >= 3
    assert all(db.disease_cases.find_one({"_id": case_id}) for case_id in cluster["case_ids"])
    assert cluster["score"] == sum(factor["points"] for factor in cluster["factors"])
    assert sum(cluster["risk_distribution"].values()) == cluster["case_count"]
    updated_case = db.disease_cases.find_one({"_id": first_id})
    assert updated_case["nearby_similar_animals"] >= 3
    assert updated_case["cluster_score"] > 0
    assert updated_case["risk"]["score"] > initial_case["risk"]["score"]
    assert updated_case["initial_risk"] == initial_case["initial_risk"]
    assert updated_case["risk"]["score"] == sum(factor["points"] for factor in updated_case["risk"]["factors"])
    before_count = db.disease_cases.count_documents({})
    db.outbreak_clusters.update_one({"_id": cluster["id"]}, {"$set": {
        "status": "confirmed_outbreak", "confirmed_by": "demo-admin", "confirmation_note": "Test professional evidence",
        "confirmed_at": utcnow(),
    }})
    refresh = client.post("/api/outbreaks/recalculate", headers=headers)
    assert refresh.status_code == 200, refresh.text
    assert db.disease_cases.count_documents({}) == before_count
    confirmed = db.outbreak_clusters.find_one({"_id": cluster["id"]})
    assert confirmed["status"] == "confirmed_outbreak"
    assert confirmed["confirmed_by"] == "demo-admin"
    assert confirmed["confirmation_note"] == "Test professional evidence"

    final = client.post("/api/demo/replay", headers=headers, json={"steps": 4})
    assert final.status_code == 200, final.text
    assert final.json()["completed"] == final.json()["total"] == 11
    final_count = db.disease_cases.count_documents({})
    exhausted = client.post("/api/demo/replay", headers=headers, json={"steps": 1})
    assert exhausted.status_code == 200, exhausted.text
    assert exhausted.json()["new_case_ids"] == []
    assert exhausted.json()["completed"] == 11
    assert db.disease_cases.count_documents({}) == final_count
    assert db.outbreak_clusters.find_one({"_id": cluster["id"]})["status"] == "confirmed_outbreak"


def test_demo_is_disabled_outside_explicit_demo_mode(client, login, monkeypatch):
    headers, _ = login("admin")
    monkeypatch.setattr(client.app.state.settings, "demo_mode", False)
    response = client.post("/api/demo/replay", headers=headers, json={"steps": 1})
    assert response.status_code in (403, 404), response.text


@pytest.mark.parametrize("path", ["/api/outbreaks", "/api/outbreaks/map?days=30"])
def test_surveillance_read_ages_out_clusters_without_a_new_report(client, login, db, monkeypatch, path):
    from app.routes import geospatial
    from app.services import outbreaks

    headers, _ = login("admin")
    replay = client.post("/api/demo/replay", headers=headers, json={"steps": 7})
    assert replay.status_code == 200, replay.text
    assert replay.json()["clusters"]
    assert db.outbreak_clusters.count_documents({"active": True}) > 0
    case_before = deepcopy(db.disease_cases.find_one({"cluster_score": {"$gt": 0}}))
    assert case_before["nearby_similar_animals"] > 0
    later = utcnow() + timedelta(hours=96)
    monkeypatch.setattr(geospatial, "utcnow", lambda: later)
    monkeypatch.setattr(outbreaks, "utcnow", lambda: later)

    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    clusters = response.json()["clusters"] if "/map" in path else response.json()
    assert clusters == [], "An unattended dashboard must not keep expired observations active indefinitely"
    assert db.outbreak_clusters.count_documents({"active": True}) == 0
    case_after = db.disease_cases.find_one({"_id": case_before["_id"]})
    assert case_after["nearby_similar_animals"] == case_after["cluster_score"] == 0
    assert case_after["risk"]["score"] < case_before["risk"]["score"]
    assert case_after["initial_risk"] == case_before["initial_risk"]
    assert all(factor["points"] == 0 for factor in case_after["risk"]["factors"]
               if factor["key"] in ("nearby_activity", "cluster_strength"))


@pytest.mark.parametrize("options", [
    {"outbreak_window_hours": 24},
    {"outbreak_window_hours": 47},
    {"outbreak_window_hours": 721},
    {"outbreak_suspected_threshold": 81},
    {"outbreak_abnormal_threshold": 65, "outbreak_suspected_threshold": 65},
])
def test_invalid_outbreak_environment_fails_before_serving_reports(options):
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="development", **options)


def test_latest_rejected_neighbor_does_not_leave_older_suspicion_in_risk(client, farmer, login, db, report_payload, animal_payload):
    target_response = client.post("/api/reports", headers=farmer[0], json=report_payload)
    assert target_response.status_code == 201, target_response.text
    neighbor_animal_payload = {**animal_payload, "name": "Nearby animal"}
    neighbor_animal_payload.pop("pashu_id", None)
    neighbor_animal = client.post("/api/animals", headers=farmer[0], json=neighbor_animal_payload)
    assert neighbor_animal.status_code == 201, neighbor_animal.text
    neighbor_report = {**report_payload, "client_report_id": str(uuid4()),
                       "animal_id": neighbor_animal.json()["id"],
                       "reported_at": (utcnow() - timedelta(hours=2)).isoformat()}
    neighbor_response = client.post("/api/reports", headers=farmer[0], json=neighbor_report)
    assert neighbor_response.status_code == 201, neighbor_response.text
    target_id = target_response.json()["id"]
    assert db.disease_cases.find_one({"_id": target_id})["nearby_similar_animals"] == 1

    # This later professional outcome supersedes that animal's older suspicion.
    rejected = deepcopy(db.disease_cases.find_one({"_id": neighbor_response.json()["id"]}))
    rejected.update({"_id": str(uuid4()), "client_report_id": str(uuid4()), "reported_at": utcnow(),
                     "confirmation_status": "rejected", "status": "rejected"})
    db.disease_cases.insert_one(rejected)
    refresh = client.post("/api/outbreaks/recalculate", headers=login("admin")[0])
    assert refresh.status_code == 200, refresh.text
    assert db.disease_cases.find_one({"_id": target_id})["nearby_similar_animals"] == 0


def test_internal_ehr_snapshot_is_not_exposed_to_test_linked_lab(client, farmer, login, db, report_payload):
    private_history = [{"case_id": "unrelated-episode", "notes": "Private prior care details"}]
    db.animals.update_one({"_id": report_payload["animal_id"]}, {"$set": {"disease_history": private_history}})
    created = client.post("/api/reports", headers=farmer[0], json=report_payload)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert db.disease_cases.find_one({"_id": case_id})["animal_snapshot"]["disease_history"] == private_history
    assert "animal_snapshot" not in created.json()
    db.lab_tests.insert_one({"_id": str(uuid4()), "case_id": case_id, "district": "Pune"})
    laboratory = client.get(f"/api/cases/{case_id}", headers=login("lab")[0])
    assert laboratory.status_code == 200, laboratory.text
    assert "animal_snapshot" not in laboratory.json()
    assert "Private prior care details" not in laboratory.text
