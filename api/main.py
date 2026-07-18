"""
api/main.py — GoldPan™ Master OS API

Run locally:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET  /health                        — liveness check
    GET  /admin/ai-usage/report         — AI cost + usage report (X-Admin-Key required)
    GET  /admin/ai-usage/controls       — raw budget_controls (X-Admin-Key required)
    GET  /admin/restaurants             — restaurant list with aggregates (X-Admin-Key required)
    GET  /admin/restaurants/{id}        — restaurant detail (X-Admin-Key required)
    GET  /admin/business-development    — BD partner pipeline list (X-Admin-Key required)
    GET  /admin/business-development/{id} — partner detail + action history (X-Admin-Key required)
    POST /admin/business-development    — create partner (X-Admin-Key required)
    PATCH /admin/business-development/{id} — update partner (X-Admin-Key required)
    POST /admin/business-development/{id}/actions — add action/note (X-Admin-Key required)
    GET  /docs                          — Swagger UI (auto-generated)
    GET  /redoc                         — ReDoc UI (auto-generated)

Environment variables (.env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    ANTHROPIC_API_KEY
    ADMIN_API_KEY                  — required for /admin/* endpoints
"""

from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ai_usage, restaurants, business_development, intake

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GoldPan™ Master OS API",
    description=(
        "Internal API for the GoldPan™ operating system. "
        "Powers AI cost tracking, Intake OS, Governance OS, and Ask GoldPan™."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (localhost only for now) ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ai_usage.router)
app.include_router(restaurants.router)
app.include_router(business_development.router)
app.include_router(intake.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "goldpan-api",
        "time": datetime.now(timezone.utc).isoformat(),
    }
