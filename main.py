import os
from dotenv import load_dotenv
import sqlite3
from fastapi import FastAPI, Response, Header
from pydantic import BaseModel
from fastapi import HTTPException
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client =create_client(SUPABASE_URL,SUPABASE_KEY) 

app = FastAPI()
DB_NAME = "tasks.db"


def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    db = get_db()

    table_exists = db.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'tasks'
        """
    ).fetchone()

    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL
        )
    """)

    db.commit()
    db.close()

    return table_exists is None


def seed_tasks():
    db = get_db()

    db.executemany(
        "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
        [
            (1, "Study", True),
            (2, "Build app", False),
            (3, "Buy groceries", False),
        ]
    )

    db.commit()
    db.close()


if init_db():
    seed_tasks()
    
@app.get("/")
def read_root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }

@app.get("/health")
def read_health():
    return {"status": "ok"}

class AuthRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/signup", status_code=201)
def signup(data: AuthRequest):
    try:
        response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password
        })

        return {
            "message": "Signup successful",
            "user": response.user
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )    
@app.post("/auth/login")
def login(data: AuthRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
@app.get("/public/info")
def public_info():
    return {
        "message": "This is a public endpoint",
        "auth_required": False
    }

# Stage 3: profile route token verification
@app.get("/protected/profile")
def protected_profile(authorization: str | None = Header(default=None)):

    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.replace("Bearer ", "", 1).strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is required"
        )

    try:
        response = supabase.auth.get_user(token)

        if response.user is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

        return {
            "message": "Protected profile accessed",
            "user": response.user
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
@app.get("/tasks")
def tasks():
    db = get_db()

    rows = db.execute(
        "SELECT id, title, done FROM tasks"
    ).fetchall()

    db.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "done": bool(row[2])
        }
        for row in rows
    ]

@app.get("/tasks/{id}")
def get_task(id: int):
    db = get_db()

    row = db.execute(
        "SELECT id, title, done FROM tasks WHERE id = ?",
        (id,)
    ).fetchone()

    db.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {id} not found"
        )

    return {
        "id": row[0],
        "title": row[1],
        "done": bool(row[2])
    }
class TaskCreate(BaseModel):
    title: str


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):

    if not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title is required"
        )

    db = get_db()

    cursor = db.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (task.title, False)
    )

    db.commit()

    new_id = cursor.lastrowid

    db.close()

    return {
        "id": new_id,
        "title": task.title,
        "done": False
    }
class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None

@app.put("/tasks/{id}")
def update_task(id: int, updated_task: TaskUpdate):

    if updated_task.title is not None:
        if not updated_task.title.strip():
            raise HTTPException(
                status_code=400,
                detail="Title is required"
            )

    db = get_db()

    row = db.execute(
        "SELECT id, title, done FROM tasks WHERE id = ?",
        (id,)
    ).fetchone()

    if row is None:
        db.close()
        raise HTTPException(
            status_code=404,
            detail=f"Task {id} not found"
        )

    new_title = (
        updated_task.title
        if updated_task.title is not None
        else row[1]
    )

    new_done = (
        updated_task.done
        if updated_task.done is not None
        else bool(row[2])
    )

    db.execute(
        """
        UPDATE tasks
        SET title = ?, done = ?
        WHERE id = ?
        """,
        (new_title, new_done, id)
    )

    db.commit()
    db.close()

    return {
        "id": id,
        "title": new_title,
        "done": new_done
    }

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):

    db = get_db()

    cursor = db.execute(
        "DELETE FROM tasks WHERE id = ?",
        (id,)
    )

    if cursor.rowcount == 0:
        db.close()
        raise HTTPException(
            status_code=404,
            detail=f"Task {id} not found"
        )

    db.commit()
    db.close()

    return Response(status_code=204)