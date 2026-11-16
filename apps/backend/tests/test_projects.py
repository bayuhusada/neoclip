import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers tables)
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_create_and_list_projects(client):
    created = client.post("/api/projects", json={"name": "  Talking Heads  "})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Talking Heads"  # stripped
    assert body["description"] is None

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert [p["name"] for p in listed.json()] == ["Talking Heads"]


def test_create_project_rejects_empty_name(client):
    assert client.post("/api/projects", json={"name": ""}).status_code == 422


def test_get_project_404(client):
    assert client.get("/api/projects/4242").status_code == 404


def test_patch_project(client):
    project_id = client.post("/api/projects", json={"name": "Old"}).json()["id"]
    patched = client.patch(f"/api/projects/{project_id}", json={"name": "New"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "New"
