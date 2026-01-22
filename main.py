from fastapi.responses import FileResponse
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form
)
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from passlib.hash import argon2
from jose import jwt, JWTError
import sqlite3
import os
import shutil
from datetime import datetime, timedelta

# -----------------------
# App & Static Setup
# -----------------------
app = FastAPI(title="Resume Management API")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------
# Security Config
# -----------------------
SECRET_KEY = "resume_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# -----------------------
# Database
# -----------------------
def get_db_connection():
    conn = sqlite3.connect("resumes.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            skills TEXT,
            experience INTEGER,
            file_path TEXT
        )
    """)

    conn.commit()
    conn.close()

# -----------------------
# Models
# -----------------------
class User(BaseModel):
    username: str
    password: str

# -----------------------
# Auth Helpers
# -----------------------
def hash_password(password: str):
    return argon2.hash(password)

def verify_password(plain, hashed):
    return argon2.verify(plain, hashed)

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# -----------------------
# Auth APIs
# -----------------------
@app.post("/signup")
def signup(user: User):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (user.username, hash_password(user.password))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")
    finally:
        conn.close()
    return {"message": "User created successfully"}

@app.post("/login")
def login(user: User):
    conn = get_db_connection()
    cursor = conn.cursor()
    db_user = cursor.execute(
        "SELECT * FROM users WHERE username=?",
        (user.username,)
    ).fetchone()
    conn.close()

    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# -----------------------
# Resume APIs
# -----------------------
@app.post("/resumes/upload")
def upload_resume(
    name: str = Form(...),
    email: str = Form(...),
    skills: str = Form(""),
    experience: str = Form("0"),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF or DOCX allowed")

    try:
        experience_int = int(experience)
    except ValueError:
        experience_int = 0

    file_location = f"{UPLOAD_DIR}/{file.filename}"

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO resumes (name, email, skills, experience, file_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, email, skills, experience_int, file_location)
    )
    conn.commit()
    conn.close()

    return {"message": "Resume uploaded successfully"}

@app.get("/resumes")
def get_resumes(user=Depends(get_current_user)):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM resumes").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/resumes/download/{resume_id}")
def download_resume(resume_id: int, user=Depends(get_current_user)):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT file_path FROM resumes WHERE id=?",
        (resume_id,)
    ).fetchone()
    conn.close()

    if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=row["file_path"],
        filename=os.path.basename(row["file_path"]),
        media_type="application/octet-stream"
    )


# -----------------------
# Frontend Routes
# -----------------------
@app.get("/ui", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.get("/list", response_class=HTMLResponse)
def list_page(request: Request):
    return templates.TemplateResponse("list.html", {"request": request})

@app.get("/")
def root():
    return {"message": "Resume Management API is live"}
