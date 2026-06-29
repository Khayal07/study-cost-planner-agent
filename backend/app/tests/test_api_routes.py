"""API-route smoke tests via FastAPI TestClient (in-memory SQLite, see conftest).

These complement the pure-logic unit tests: they assert the HTTP contract of the
public meta/auth/applications endpoints and that auth gates are enforced. They run
against an empty DB (no seed), so they exercise structure and error paths rather
than full planning output.
"""
from __future__ import annotations


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm_enabled" in body


def test_meta_options_shape_on_empty_db(client):
    r = client.get("/meta/options")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"countries", "fields", "report_currencies", "default_report_currency"}
    # Base report currencies are always offered even with no data seeded.
    assert "EUR" in body["report_currencies"]


def test_meta_stats_zero_on_empty_db(client):
    r = client.get("/meta/stats")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "countries": 0,
        "universities": 0,
        "programs": 0,
        "cited_figures": 0,
        "sourced_figures": 0,
        "scholarships": 0,
    }


def test_register_login_me_flow(client):
    reg = client.post("/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert reg.status_code == 200
    token = reg.json()["token"]
    assert reg.json()["user"]["email"] == "a@b.com"

    # Duplicate email -> 409.
    dup = client.post("/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert dup.status_code == 409

    # Wrong password -> 401.
    bad = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/auth/login", json={"email": "a@b.com", "password": "secret123"})
    assert ok.status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_applications_require_auth(client):
    assert client.get("/applications").status_code == 401


def test_application_crud_roundtrip(client):
    token = client.post(
        "/auth/register", json={"email": "c@d.com", "password": "secret123"}
    ).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/applications", headers=auth).json() == []

    created = client.post(
        "/applications",
        headers=auth,
        json={"scholarship_name": "DAAD", "provider": "DAAD", "documents": ["CV", "Transcript"]},
    )
    assert created.status_code == 201
    app_id = created.json()["id"]
    assert len(created.json()["documents"]) == 2

    updated = client.patch(f"/applications/{app_id}", headers=auth, json={"status": "submitted"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "submitted"

    # Invalid status -> rejected.
    bad = client.patch(f"/applications/{app_id}", headers=auth, json={"status": "bogus"})
    assert bad.status_code in (400, 422)

    deleted = client.delete(f"/applications/{app_id}", headers=auth)
    assert deleted.status_code == 204
    assert client.get("/applications", headers=auth).json() == []
