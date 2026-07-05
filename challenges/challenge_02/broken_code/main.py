from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Todo API")


class TodoCreate(BaseModel):
    title: str
    completed: bool = False


class Todo(TodoCreate):
    id: int


_todos: dict[int, Todo] = {}
_next_id = 1


@app.get("/todos")
def list_todos():
    return list(_todos.values())


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int):
    todo = _todos.get(todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@app.post("/todos", status_code=201)
def create_todo(payload: TodoCreate):
    global _next_id
    todo = Todo(id=_next_id, **payload.model_dump())
    _todos[_next_id] = todo
    _next_id += 1
    return todo

# DELETE /todos/{todo_id} is missing — that's the challenge.
