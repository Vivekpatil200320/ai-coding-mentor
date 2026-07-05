from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_todos_starts_empty():
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []


def test_create_todo():
    response = client.post("/todos", json={"title": "Buy milk"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Buy milk"
    assert body["completed"] is False


def test_get_existing_todo():
    created = client.post("/todos", json={"title": "Walk dog"}).json()
    response = client.get(f"/todos/{created['id']}")
    assert response.status_code == 200


def test_delete_existing_todo_returns_204():
    created = client.post("/todos", json={"title": "Read book"}).json()
    response = client.delete(f"/todos/{created['id']}")
    assert response.status_code == 204


def test_deleted_todo_is_gone():
    created = client.post("/todos", json={"title": "Clean house"}).json()
    client.delete(f"/todos/{created['id']}")
    response = client.get(f"/todos/{created['id']}")
    assert response.status_code == 404


def test_delete_nonexistent_todo_returns_404():
    response = client.delete("/todos/9999")
    assert response.status_code == 404


def test_delete_does_not_break_existing_endpoints():
    client.post("/todos", json={"title": "Keep me"})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
