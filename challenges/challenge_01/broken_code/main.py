from fastapi import FastAPI

app = FastAPI(title="User Directory API")

USERS = {
    1: {"id": 1, "name": "Ada Lovelace", "email": "ada@example.com"},
    2: {"id": 2, "name": "Alan Turing", "email": "alan@example.com"},
    3: {"id": 3, "name": "Grace Hopper", "email": "grace@example.com"},
}


@app.get("/users")
def list_users():
    return list(USERS.values())


@app.get("/users/{user_id}")
def get_user(user_id: int):
    return USERS[user_id]
