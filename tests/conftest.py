"""API fixtures use an explicit test database, never an implicit runtime fallback."""

from copy import deepcopy
from uuid import uuid4

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routes.auth import _attempts, _lock
from app.services.seed import seed_demo


@pytest.fixture(autouse=True)
def isolate_auth_rate_limiter():
    with _lock:
        _attempts.clear()
    yield
    with _lock:
        _attempts.clear()


@pytest.fixture
def db():
    database = mongomock.MongoClient(tz_aware=True)["pashuraksha_test"]
    seed_demo(database)
    yield database
    database.client.close()


@pytest.fixture
def client(db):
    with TestClient(create_app(db)) as test_client:
        yield test_client


@pytest.fixture
def login(client):
    def authenticate(role="farmer"):
        response = client.post(
            "/api/auth/login",
            json={"email": f"{role}@demo.pashuraksha.in", "password": "Demo@26128"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    return authenticate


@pytest.fixture
def farmer(login):
    return login("farmer")


@pytest.fixture
def animal_payload(farmer):
    _, user = farmer
    return {
        "name": "Test Gauri",
        "pashu_id": str(uuid4().int % 900_000_000_000 + 100_000_000_000),
        "species": "cattle",
        "breed": "Gir",
        "age_months": 36,
        "gender": "female",
        "location": {"type": "Point", "coordinates": [73.985, 18.515]},
        "village": "Test Village",
        "district": user["district"],
    }


@pytest.fixture
def owned_animal(client, farmer, animal_payload):
    headers, _ = farmer
    response = client.post("/api/animals", json=animal_payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def report_payload(owned_animal):
    return {
        "client_report_id": str(uuid4()),
        "animal_id": owned_animal["id"],
        "symptoms": ["fever", "skin_lesions", "swelling"],
        "temperature_c": 40.0,
        "appetite": "reduced",
        "milk_drop_percent": 25,
        "activity": "reduced",
        "recent_contact": True,
        "vaccination_status": "overdue",
        "mortality_count": 0,
        "duration_hours": 24,
        "location": deepcopy(owned_animal["location"]),
    }


@pytest.fixture
def other_farmer(client, farmer):
    _, user = farmer
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Another Farmer",
            "email": f"other-{uuid4().hex}@example.org",
            "password": "Another@26128",
            "district": user["district"],
        },
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]
