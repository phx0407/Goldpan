"""
api/tests/conftest.py — shared pytest setup for the focused Tasks #43/#44
Intake claim/release/approve/return test suites.

api/tests/test_intake_claim_release.py and api/tests/test_intake_review_
decisions.py both need a real FastAPI `app` with intake.router mounted (and
its dependency-override machinery) to drive TestClient(app) against the real
endpoint wiring for operations.claim_intake_packet / release_intake_packet /
approve_intake_packet / return_intake_packet (supabase/migrations/017 and
018).

`app` here mounts api.routers.intake.router only, under that router's own
prefix ("/admin/intake", set in api/routers/intake.py) — i.e. the same route
prefix the real application serves these endpoints under. It intentionally
does not import or mount api.main or the unrelated ai_usage/restaurants/
business_development routers: api/main.py and those routers are not part of
the scoped Tasks #43/#44 commit (this repo's api/ directory has never been
committed to git), and pulling them in merely to satisfy an import chain
would silently widen the commit's scope beyond intake.

When api/main.py and the rest of api/ are committed for real, the two test
files above should be switched back to `from api.main import app` and this
module's `app` definition can be removed.
"""

from fastapi import FastAPI

from api.routers import intake

app = FastAPI(title="GoldPan Intake OS API (focused test setup)")
app.include_router(intake.router)
