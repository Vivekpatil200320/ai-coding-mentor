from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_users_returns_all_users():
    response = client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_existing_user_returns_200():
    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Ada Lovelace"


def test_get_missing_user_returns_404_not_500():
    response = client.get("/users/999")
    assert response.status_code == 404


def test_get_missing_user_has_error_detail():
    response = client.get("/users/999")
    assert "detail" in response.json()
