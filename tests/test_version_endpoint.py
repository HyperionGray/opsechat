"""Tests for the /version endpoint."""


def test_version_endpoint_returns_version_field():
    from app_factory import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/version")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, dict)
    assert "version" in data
    assert isinstance(data["version"], str)
    assert data["version"]
