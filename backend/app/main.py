import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CivicAssist API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    """Report API process health."""
    return {"status": "ok"}
