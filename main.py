import hashlib
from passlib.hash import bcrypt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
import sqlite3
from datetime import datetime, timedelta

app = FastAPI(title="Resume Management API")

# -----------------------
# Security settings
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
            experience INTEGER
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

class Resume(BaseModel):
    name: str
    email: str
    skills: str
    experience: int

# -----------------------
# Utility functions
# -----------------------
def hash_password(password: str):
    sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return bcrypt.using(rounds=12).hash(sha)


def verify_password(plain, hashed):
    sha = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return bcrypt.verify(sha, hashed)




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
# Public Routes
# -----------------------
@app.get("/")
def root():
    return {"message": "Resume Management API is live"}

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
        "SELECT * FROM users WHERE username=?", (user.username,)
    ).fetchone()
    conn.close()

    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# -----------------------
# Protected Resume APIs
# -----------------------
@app.post("/resumes")
def add_resume(resume: Resume, user=Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resumes (name, email, skills, experience) VALUES (?, ?, ?, ?)",
        (resume.name, resume.email, resume.skills, resume.experience)
    )
    conn.commit()
    conn.close()
    return {"message": "Resume added"}

@app.get("/resumes")
def get_resumes(user=Depends(get_current_user)):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM resumes").fetchall()
    conn.close()
    return [dict(row) for row in rows]
