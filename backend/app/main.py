import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="AegisAI", version="0.1.0")


@app.get("/health/live")
def live():
    return {"status": "ok", "service": "aegisai-api"}


@app.get("/health/ready")
def ready():
    try:
        with psycopg.connect(
            host="db",
            dbname="aegisai",
            user="aegisai_app",
            password=os.environ["APP_DB_PASSWORD"],
            connect_timeout=3,
            options="-c statement_timeout=3000",
        ) as conn:
            result = conn.execute("SELECT 1").fetchone()
            if result != (1,):
                raise HTTPException(503, "Database unavailable")
    except psycopg.Error:
        raise HTTPException(503, "Database unavailable") from None

    return {"status": "ok", "database": "connected"}


from fastapi.responses import JSONResponse
from app.auth import router as auth_router

app.include_router(auth_router)


@app.exception_handler(psycopg.Error)
async def database_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable"},
    )


from app.audit import audit_middleware
app.middleware("http")(audit_middleware)


from app.security_routes import router as security_router
app.include_router(security_router)


from app.workflow import router as workflow_router
app.include_router(workflow_router)


from app.agents import router as agents_router
app.include_router(agents_router)


from app.analysis_proposals import router as analysis_proposals_router
app.include_router(analysis_proposals_router)


from app.chat import router as chat_router
app.include_router(chat_router)
