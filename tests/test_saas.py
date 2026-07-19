"""Tests for GenAI SaaS Backend"""
import os, pytest, uuid, tempfile

# Must set DATABASE_URL before any imports from backend
_tmp_db = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# Now import backend after env vars are set
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Base, PLAN_LIMITS, PlanType

# Create a fresh engine pointing to our temp DB
test_engine = create_engine(f"sqlite:///{_tmp_db}", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

# Patch the models module to use test engine
import backend.db.models as models_module
models_module.engine = test_engine
models_module.SessionLocal = TestSessionLocal

def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

models_module.get_db = get_test_db

from fastapi.testclient import TestClient
import backend.main as main_module
main_module.app.dependency_overrides = {}

from fastapi import Depends
from backend.main import app, get_db as original_get_db
app.dependency_overrides[original_get_db] = get_test_db

client = TestClient(app)

def make_user(email=None):
    email = email or f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "name": "Test User", "password": "password123"})
    return r.json(), email

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_register():
    data, email = make_user()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["plan"] == "free"

def test_register_duplicate_email():
    _, email = make_user()
    r = client.post("/api/auth/register", json={"email": email, "name": "Test", "password": "pass123"})
    assert r.status_code == 400

def test_login():
    _, email = make_user()
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_login_wrong_password():
    _, email = make_user()
    r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401

def test_get_me():
    data, _ = make_user()
    token = data["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "email" in r.json()
    assert "api_key" in r.json()

def test_create_project():
    data, _ = make_user()
    token = data["access_token"]
    r = client.post("/api/projects", json={"title": "My Research"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["title"] == "My Research"

def test_list_projects():
    data, _ = make_user()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/projects", json={"title": "P1"}, headers=headers)
    client.post("/api/projects", json={"title": "P2"}, headers=headers)
    r = client.get("/api/projects", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 2

def test_project_limit_free_plan():
    data, _ = make_user()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(3):
        r = client.post("/api/projects", json={"title": f"P{i}"}, headers=headers)
        assert r.status_code == 200
    r = client.post("/api/projects", json={"title": "P4"}, headers=headers)
    assert r.status_code == 403

def test_delete_project():
    data, _ = make_user()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/projects", json={"title": "Delete Me"}, headers=headers)
    pid = r.json()["id"]
    r2 = client.delete(f"/api/projects/{pid}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["deleted"] is True

def test_dashboard():
    data, _ = make_user()
    token = data["access_token"]
    r = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "usage" in r.json()
    assert "plan" in r.json()

def test_get_plans():
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert len(plans) == 3
    names = [p["name"] for p in plans]
    assert "Free" in names and "Pro" in names and "Enterprise" in names

def test_upgrade_plan():
    data, _ = make_user()
    token = data["access_token"]
    r = client.post("/api/billing/upgrade", json={"plan": "pro"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["plan"] == "pro"

def test_unauthenticated_access():
    r = client.get("/api/projects")
    assert r.status_code == 401

def test_api_key_auth():
    data, _ = make_user()
    token = data["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    api_key = me["api_key"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 200
