from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3

app = FastAPI(title="Resume Management API")

# -----------------------
# Database connection
# -----------------------
def get_db_connection():
    conn = sqlite3.connect("resumes.db")
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------
# Create table on startup
# -----------------------
@app.on_event("startup")
def startup():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            skills TEXT,
            experience INTEGER
        )
    """)
    conn.commit()
    conn.close()

# -----------------------
# Models
# -----------------------
class Resume(BaseModel):
    name: str
    email: str
    skills: str
    experience: int

# -----------------------
# Routes
# -----------------------
@app.get("/")
def root():
    return {"message": "Resume Management API is live"}

@app.get("/health")
def health_check():
    return {"status": "OK"}

@app.post("/resumes")
def add_resume(resume: Resume):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resumes (name, email, skills, experience) VALUES (?, ?, ?, ?)",
        (resume.name, resume.email, resume.skills, resume.experience)
    )
    conn.commit()
    conn.close()
    return {"message": "Resume added successfully"}

@app.get("/resumes")
def get_resumes():
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM resumes").fetchall()
    conn.close()
    return [dict(row) for row in rows]

