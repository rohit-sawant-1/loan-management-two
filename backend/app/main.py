"""
The server. `uvicorn app.main:app --reload --port 8000` runs it, and the
trainer's tests import `app` from here.

Everything is wired together in this one file: settings, logging, tracing,
the database, CORS, the request middleware, and every router at its
/api/v1/... address.
"""

from contextlib import asynccontextmanager

import structlog
from dotenv import load_dotenv

# The observability guide insists on this before anything else reads the
# environment. Settings already read .env, but this costs nothing.
load_dotenv()

from fastapi import FastAPI                                  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware           # noqa: E402
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402

from app.config import settings                              # noqa: E402
from app.database import engine, init_db                     # noqa: E402
from app.middleware.logging_middleware import logging_middleware  # noqa: E402
from app.routers import (                                     # noqa: E402
    activity, admin, applicants, applications, auth, briefing, chat, dashboard, documents,
    edit_requests, eligibility, notifications, settings as settings_router,
)
from app.utils.logging_config import configure_logging       # noqa: E402
from app.utils.otel_config import instrument_sqlalchemy, setup_telemetry  # noqa: E402

configure_logging()
setup_telemetry()
instrument_sqlalchemy(engine)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup and once at shutdown."""
    init_db()
    # In structlog the first argument IS the event name. The trainer's sample
    # passes event= as well, which crashes with "multiple values for event" (T-35).
    logger.info("database_initialized", operation="startup", app_env=settings.app_env)
    yield
    logger.info("application_stopped", operation="shutdown")


app = FastAPI(
    title="Loan Application Management API",
    description="POC-01 for the Agentic AI Readiness Program. Phase 1: the loan application system.",
    version="0.1.0",
    lifespan=lifespan,
)

# The browser will refuse to let React on port 5173 call an API on port 8000
# unless the API says it is allowed. The trainer's doc says 3000; that is the
# old Create React App port and would make the front-end unable to reach us (T-17).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Request id, timing, and JSON logs around every request.
app.middleware("http")(logging_middleware)

# One http.request span per request, automatically.
FastAPIInstrumentor.instrument_app(app)

# The addresses. Paths inside each router never end in "/" (T-02).
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(applicants.router, prefix="/api/v1/applicants", tags=["applicants"])
app.include_router(eligibility.router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(documents.router, prefix="/api/v1/applications", tags=["documents"])
# Piece 25: a customer asks to change their application, staff approve or refuse.
app.include_router(edit_requests.router, prefix="/api/v1/applications", tags=["edit requests"])
app.include_router(edit_requests.staff_router, prefix="/api/v1/edit-requests", tags=["edit requests"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])
# Piece 27: the System Administrator's own screens.
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
# Piece 28: every signed-in screen reads the settings; only the admin changes them.
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
# Piece 30: the bell. Everyone reads their own, and only their own.
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
# The headline feature (D-13): the manager's morning briefing.
app.include_router(briefing.router, prefix="/api/v1/briefing", tags=["briefing"])
# The one chat door. What sits behind it grows with each phase; the address does not.
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.get("/health", tags=["health"])
def health():
    """The reviewer's guide checks this with curl after starting the server."""
    return {"status": "ok", "app": settings.app_name, "phase": settings.phase}
