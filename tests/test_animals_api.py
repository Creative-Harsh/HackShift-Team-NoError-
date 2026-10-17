from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def test_farmer_animal_creation_and_simulated_lookup(client, farmer, owned_animal):
    headers, user = farmer
    assert owned_animal["owner_id"] == user["id"]
    assert len(owned_animal["pashu_id"]) == 12
    assert owned_animal["pashu_id"].isdigit()
    response = client.get(f"/api/animals/pashu-id/{owned_animal['pashu_id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == owned_animal["id"]
    assert {"vaccination_history", "disease_history", "treatment_history", "lab_history", "health_status"} <= response.json().keys()
    assert owned_animal["id"] in {a["id"] for a in client.get("/api/animals", headers=headers).json()}


def test_generated_identity_has_twelve_digits(client, farmer, animal_payload):
    headers, _ = farmer
    animal_payload.pop("pashu_id")
    response = client.post("/api/animals", json=animal_payload, headers=headers)
    assert response.status_code == 201, response.text
    assert len(response.json()["pashu_id"]) == 12
    assert response.json()["pashu_id"].isdigit()


@pytest.mark.parametrize("pashu_id", ["123", "12345678901A", "1234567890123"])
def test_invalid_simulated_identity_rejected(client, farmer, animal_payload, pashu_id):
    animal_payload["pashu_id"] = pashu_id
    assert client.post("/api/animals", json=animal_payload, headers=farmer[0]).status_code == 422


def test_duplicate_identity_rejected(client, farmer, animal_payload, owned_animal):
    animal_payload["pashu_id"] = owned_animal["pashu_id"]
    assert client.post("/api/animals", json=animal_payload, headers=farmer[0]).status_code == 409


@pytest.mark.parametrize(
    "location",
    [
        {"type": "Point", "coordinates": [181, 18]},
        {"type": "Point", "coordinates": [73, -91]},
        {"type": "Point", "coordinates": [73]},
        {"type": "Point", "coordinates": [73, 18, 4]},
        {"type": "LineString", "coordinates": [73, 18]},
    ],
)
def test_invalid_geojson_rejected(client, farmer, animal_payload, location):
    animal_payload["location"] = location
    response = client.post("/api/animals", json=animal_payload, headers=farmer[0])
    assert response.status_code == 422, response.text


def test_farmer_cannot_access_another_owners_animal(client, other_farmer, owned_animal):
    headers, _ = other_farmer
    for path in (
        f"/api/animals/{owned_animal['id']}",
        f"/api/animals/{owned_animal['id']}/history",
        f"/api/animals/pashu-id/{owned_animal['pashu_id']}",
    ):
        assert client.get(path, headers=headers).status_code in (403, 404)
    response = client.get("/api/animals", headers=headers)
    assert response.status_code == 200
    assert owned_animal["id"] not in {animal["id"] for animal in response.json()}


def test_farmer_cannot_set_another_owner(client, farmer, other_farmer, animal_payload):
    animal_payload["owner_id"] = other_farmer[1]["id"]
    response = client.post("/api/animals", json=animal_payload, headers=farmer[0])
    assert response.status_code in (403, 422)


@pytest.mark.parametrize("role", ["lab", "vet"])
def test_non_reporting_roles_cannot_create_animals(client, login, role, animal_payload):
    headers, _ = login(role)
    assert client.post("/api/animals", json=animal_payload, headers=headers).status_code == 403


def test_paravet_can_create_for_district_farmer(client, login, farmer, animal_payload):
    headers, _ = login("paravet")
    animal_payload["owner_id"] = farmer[1]["id"]
    response = client.post("/api/animals", json=animal_payload, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["owner_id"] == farmer[1]["id"]


@pytest.mark.parametrize("role", ["paravet", "vet", "admin"])
def test_professional_district_boundary(client, login, db, owned_animal, role):
    headers, _ = login(role)
    foreign = deepcopy(db.animals.find_one({"_id": owned_animal["id"]}))
    assert foreign is not None
    foreign["_id"] = str(uuid4())
    foreign["pashu_id"] = str(uuid4().int % 900_000_000_000 + 100_000_000_000)
    foreign["district"] = "Outside Test District"
    db.animals.insert_one(foreign)
    assert client.get(f"/api/animals/{foreign['_id']}", headers=headers).status_code in (403, 404)
    assert foreign["_id"] not in {a["id"] for a in client.get("/api/animals", headers=headers).json()}


def test_vaccination_is_professional_record_and_appears_in_history(client, farmer, login, owned_animal):
    now = datetime.now(timezone.utc)
    payload = {"vaccine": "FMD demo record", "date_given": now.date().isoformat(), "next_due_date": (now + timedelta(days=180)).date().isoformat()}
    path = f"/api/animals/{owned_animal['id']}/vaccinations"
    assert client.post(path, json=payload, headers=farmer[0]).status_code == 403
    headers, _ = login("paravet")
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code in (200, 201), response.text
    history = client.get(f"/api/animals/{owned_animal['id']}/history", headers=farmer[0])
    assert history.status_code == 200
    assert any(record["vaccine"] == payload["vaccine"] for record in history.json()["animal"]["vaccination_history"])


def test_lab_only_reads_test_linked_cases_and_embedded_histories(client, farmer, login, db, report_payload, owned_animal):
    linked = client.post("/api/reports", json=report_payload, headers=farmer[0]).json()
    unrelated_payload = {**report_payload, "client_report_id": str(uuid4())}
    unrelated = client.post("/api/reports", json=unrelated_payload, headers=farmer[0]).json()
    db.lab_tests.insert_one({"_id": "accessible-test", "case_id": linked["id"], "district": "Pune"})
    db.lab_tests.insert_one({"_id": "outside-district-test", "case_id": linked["id"], "district": "Other District"})
    db.animals.update_one({"_id": owned_animal["id"]}, {"$set": {
        key: [{"case_id": linked["id"], "note": "Accessible"},
              {"case_id": unrelated["id"], "note": "Private episode"},
              {"note": "Unlinked private episode"}]
        for key in ("disease_history", "treatment_history", "lab_history")
    }})
    db.animals.update_one({"_id": owned_animal["id"]}, {"$push": {
        "lab_history": {"case_id": linked["id"], "district": "Other District", "note": "Outside district result"}
    }})
    headers, _ = login("lab")
    response = client.get(f"/api/animals/{owned_animal['id']}/history", headers=headers)
    assert response.status_code == 200, response.text
    history = response.json()
    assert [case["id"] for case in history["cases"]] == [linked["id"]]
    assert [test["id"] for test in history["lab_tests"]] == ["accessible-test"]
    for key in ("disease_history", "treatment_history", "lab_history"):
        assert history["animal"][key] == [{"case_id": linked["id"], "note": "Accessible"}]
    assert client.get(f"/api/cases/{unrelated['id']}", headers=headers).status_code == 404
    for path in (f"/api/animals/{owned_animal['id']}", f"/api/animals/pashu-id/{owned_animal['pashu_id']}"):
        detail = client.get(path, headers=headers)
        assert detail.status_code == 200
        assert "Private episode" not in detail.text
        assert "Unlinked private episode" not in detail.text
        assert "Outside district result" not in detail.text
    listing = client.get("/api/animals", headers=headers)
    assert listing.status_code == 200
    assert "Private episode" not in listing.text
    assert "Unlinked private episode" not in listing.text
    assert "Outside district result" not in listing.text
    # Redaction must not mutate the persisted farmer/professional EHR.
    assert len(db.animals.find_one({"_id": owned_animal["id"]})["disease_history"]) == 3


def test_lab_cannot_read_animal_without_test_request(client, login, owned_animal):
    headers, _ = login("lab")
    for path in (f"/api/animals/{owned_animal['id']}", f"/api/animals/{owned_animal['id']}/history",
                 f"/api/animals/pashu-id/{owned_animal['pashu_id']}"):
        assert client.get(path, headers=headers).status_code == 404
    assert owned_animal["id"] not in {animal["id"] for animal in client.get("/api/animals", headers=headers).json()}
