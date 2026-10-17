"""Explicit opt-in checks against MongoDB, separate from mongomock API tests.

Only a uniquely generated test database is created and dropped. This module
never uses or clears the configured application database.
"""

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from app.main import create_app
from app.database import utcnow

pytestmark = pytest.mark.mongo


@pytest.fixture
def real_database():
    uri = os.environ.get("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("Set MONGODB_TEST_URI to run against a real MongoDB instance")
    database_name = "pashuraksha_test_" + uuid4().hex
    connection = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    connection.admin.command("ping")
    database = connection[database_name]
    try:
        yield database
    finally:
        assert database.name == database_name
        assert database_name.startswith("pashuraksha_test_")
        assert len(database_name.removeprefix("pashuraksha_test_")) == 32
        connection.drop_database(database_name)
        connection.close()


def test_real_mongo_auth_ehr_report_roundtrip_and_geo_indexes(real_database):
    db = real_database
    with TestClient(create_app(db)) as client:
        account = {"name": "Integration Farmer", "email": f"mongo-{uuid4().hex}@example.org",
                   "password": "Integration@26128", "district": "Pune"}
        registration = client.post("/api/auth/register", json=account)
        assert registration.status_code == 201, registration.text
        credentials = {key: account[key] for key in ("email", "password")}
        login = client.post("/api/auth/login", json=credentials)
        assert login.status_code == 200, login.text
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.get("/api/auth/me", headers=headers).json()["email"] == account["email"]

        animal = {"name": "Real Mongo Gauri", "species": "cattle", "breed": "Gir", "age_months": 24,
                  "gender": "female", "location": {"type": "Point", "coordinates": [73.685, 18.725]},
                  "village": "Shirgaon", "district": "Pune"}
        created = client.post("/api/animals", json=animal, headers=headers)
        assert created.status_code == 201, created.text
        identity = created.json()
        lookup = client.get(f"/api/animals/pashu-id/{identity['pashu_id']}", headers=headers)
        assert lookup.status_code == 200
        assert lookup.json()["id"] == identity["id"]

        report = {"client_report_id": str(uuid4()), "animal_id": identity["id"],
                  "symptoms": ["fever", "skin_lesions"], "temperature_c": 40,
                  "appetite": "reduced", "milk_drop_percent": 20, "activity": "reduced",
                  "recent_contact": True, "vaccination_status": "overdue", "mortality_count": 0,
                  "duration_hours": 12, "location": animal["location"]}
        reported = client.post("/api/reports", json=report, headers=headers)
        assert reported.status_code == 201, reported.text
        retry = client.post("/api/reports", json=report, headers=headers)
        assert retry.status_code == 200, retry.text
        assert retry.json()["id"] == reported.json()["id"]
        stored = db.disease_cases.find_one({"_id": reported.json()["id"]})
        assert stored["location"] == animal["location"]
        assert stored["reported_at"].tzinfo is not None
        assert db.disease_cases.count_documents({"animal_id": identity["id"]}) == 1
        assert db.animals.find_one({"_id": identity["id"]})["health_status"] == "under_observation"
        history = client.get(f"/api/animals/{identity['id']}/history", headers=headers)
        assert history.status_code == 200
        assert reported.json()["id"] in {case["id"] for case in history.json()["cases"]}

        for collection, field in ((db.animals, "location"), (db.disease_cases, "location"),
                                  (db.outbreak_clusters, "center")):
            assert any(list(index["key"].items()) == [(field, "2dsphere")]
                       for index in collection.list_indexes())
        duplicate = {**stored, "_id": str(uuid4())}
        with pytest.raises(DuplicateKeyError):
            db.disease_cases.insert_one(duplicate)

        assert client.post("/api/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_real_mongo_near_respects_distance_time_disease_and_access_scope(real_database):
    db = real_database
    center = [73.68, 18.72]
    now = utcnow()

    def create_geo_case(offset, *, owner="demo-farmer", district="Pune", disease="lsd", hours_ago=1):
        identifier = str(uuid4())
        db.disease_cases.insert_one({
            "_id": identifier, "client_report_id": str(uuid4()), "reporter_id": owner,
            "animal_id": "geo-animal-" + identifier, "owner_id": owner, "district": district,
            "village": "Shirgaon", "species": "cattle", "status": "triage", "confirmation_status": "suspected",
            "location": {"type": "Point", "coordinates": [center[0] + offset, center[1]]},
            "reported_at": now - timedelta(hours=hours_ago), "created_at": now, "updated_at": now,
            "triage": {"disease_code": disease, "suspected_disease": "Possible " + disease},
            "risk": {"score": 60, "level": "HIGH", "factors": [], "version": "test-fixture"},
        })
        return identifier

    with TestClient(create_app(db)) as client:
        nearby = create_geo_case(.001)
        within_five_km = create_geo_case(.04, owner="demo-farmer-b", hours_ago=48)
        create_geo_case(.07)  # Roughly 7.4 km away, outside the query's 5 km radius.
        create_geo_case(.002, hours_ago=240)
        create_geo_case(.002, hours_ago=-1)
        create_geo_case(.002, disease="fmd")
        create_geo_case(.002, district="Other District", owner="demo-farmer-b")

        def headers_for(role):
            response = client.post("/api/auth/login", json={
                "email": f"{role}@demo.pashuraksha.in", "password": "Demo@26128",
            })
            assert response.status_code == 200, response.text
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        admin = headers_for("admin")
        parameters = {"longitude": center[0], "latitude": center[1], "radius_km": 5, "days": 3, "disease": "lsd"}
        response = client.get("/api/cases/nearby", params=parameters, headers=admin)
        assert response.status_code == 200, response.text
        assert {case["id"] for case in response.json()} == {nearby, within_five_km}
        tighter = client.get("/api/cases/nearby", params={**parameters, "radius_km": 1}, headers=admin)
        assert tighter.status_code == 200, tighter.text
        assert {case["id"] for case in tighter.json()} == {nearby}
        recent = client.get("/api/cases/nearby", params={**parameters, "days": 1}, headers=admin)
        assert {case["id"] for case in recent.json()} == {nearby}
        owned = client.get("/api/cases/nearby", params=parameters, headers=headers_for("farmer"))
        assert owned.status_code == 200, owned.text
        assert {case["id"] for case in owned.json()} == {nearby}
