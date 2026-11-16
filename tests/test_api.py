import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import create_app

def test_health():
    app = create_app()
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_stations():
    app = create_app()
    client = app.test_client()
    response = client.get("/api/v1/stations")
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json["data"]) > 0
