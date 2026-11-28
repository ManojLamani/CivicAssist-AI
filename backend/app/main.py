import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import router as auth_router
from app.complaints import router as complaint_router
from app.config import get_auth_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_auth_settings()  # Fail startup if the signing secret is missing or too short.
    yield


app = FastAPI(title="CivicAssist API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(auth_router)
app.include_router(complaint_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Validation errors must not echo submitted passwords or other request data.
    errors = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    """Report API process health."""
    return {"status": "ok"}
