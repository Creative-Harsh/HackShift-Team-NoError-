from uuid import uuid4

import pytest


def test_database_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert {"status", "database", "demo_mode"} <= response.json().keys()


@pytest.mark.parametrize("role", ["farmer", "paravet", "vet", "lab", "admin"])
def test_each_seeded_role_can_login_and_get_me(client, login, role):
    headers, user = login(role)
    assert user["role"] == role
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert not {"password", "password_hash", "hashed_password"} & response.json().keys()


def test_registration_creates_farmer_and_hashes_password(client, db):
    email = f"new-{uuid4().hex}@example.org"
    password = "Secure@26128"
    response = client.post(
        "/api/auth/register",
        json={"name": "New Farmer", "email": email, "password": password, "district": "Pune"},
    )
    assert response.status_code in (200, 201), response.text
    result = response.json()
    assert result["user"]["role"] == "farmer"
    assert "access_token" in result
    stored = db.users.find_one({"email": email})
    assert stored is not None
    assert password not in str(stored)
    assert "$argon2" in str(stored)
    assert password not in response.text


@pytest.mark.parametrize("role", ["admin", "vet", "lab", "paravet"])
def test_public_registration_cannot_choose_privileged_role(client, role):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Escalation Attempt",
            "email": f"unauthorized-{uuid4().hex}@example.org",
            "password": "Secure@26128",
            "district": "Pune",
            "role": role,
        },
    )
    assert response.status_code == 422


def test_duplicate_normalized_email_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Duplicate",
            "email": "FARMER@DEMO.PASHURAKSHA.IN",
            "password": "Secure@26128",
            "district": "Pune",
        },
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "farmer@demo.pashuraksha.in", "password": "WrongPassword!"},
        {"email": "absent@example.org", "password": "WrongPassword!"},
    ],
)
def test_bad_credentials_rejected_without_account_detail(client, credentials):
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_logout_revokes_existing_token(client, farmer):
    headers, _ = farmer
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    response = client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/animals", headers=headers).status_code == 401


def test_login_rate_limit_rejects_excess_attempts(client):
    credentials = {"email": "absent@example.org", "password": "WrongPassword!"}
    for _ in range(30):
        assert client.post("/api/auth/login", json=credentials).status_code == 401
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/animals", "/api/cases"])
def test_protected_endpoints_require_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer forged-token"}).status_code == 401
