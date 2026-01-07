from fastapi import FastAPI

app = FastAPI(title="Resume Management API")

@app.get("/")
def root():
    return {"message": "Resume Management API is live"}

@app.get("/health")
def health_check():
    return {"status": "OK"}
