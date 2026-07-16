"""
api/role_adapter.py — Interim DB-role → Blueprint-role adapter

⚠ TECHNICAL DEBT / IMPLEMENTATION ADAPTER — NOT A PERMANENT ROLE MODEL.

`operations.users.role` (migration 004) is constrained to
`canvasser | reviewer | coordinator | admin` — a legacy enum that predates
the Master OS Blueprint's role vocabulary (Governance Reviewer, Intake
Specialist, Administrator, etc.). This module is a temporary, isolated
mapping layer between that legacy DB enum and the Blueprint roles referenced
by DEC000001/DEC000002 endpoint logic.

Interim mapping (per Brad's implementation direction, DEC000001 Implementation
Gap Map §4):
  reviewer    → Governance Reviewer   (may claim/approve/return/reject packets)
  canvasser   → Intake Specialist     (may edit_payload/resubmit; never reviews)
  admin       → Administrator         (authorized override role, e.g. release-override)
  coordinator → no automatic review or evidence-mutation authority

Do NOT treat these mappings as GoldPan's permanent role definitions. They
exist only so endpoint code (api/routers/*.py) can ask role-shaped questions
("can this actor claim a review?") without embedding raw DB role strings.
When real per-user Supabase Auth + a proper role model land, this module
should be replaced wholesale — callers depend only on the functions below,
never on the mapping dict or the raw `operations.users.role` string, so that
swap should not require touching endpoint logic.
"""

from enum import Enum


class BlueprintRole(str, Enum):
    GOVERNANCE_REVIEWER = "governance_reviewer"
    INTAKE_SPECIALIST   = "intake_specialist"
    ADMINISTRATOR       = "administrator"
    NONE                = "none"


# Interim, explicitly-temporary adapter mapping. See module docstring.
_DB_ROLE_TO_BLUEPRINT_ROLE = {
    "reviewer":    BlueprintRole.GOVERNANCE_REVIEWER,
    "canvasser":   BlueprintRole.INTAKE_SPECIALIST,
    "admin":       BlueprintRole.ADMINISTRATOR,
    "coordinator": BlueprintRole.NONE,
}


def blueprint_role_for(db_role: str) -> BlueprintRole:
    """Map a raw operations.users.role string to its interim Blueprint role."""
    return _DB_ROLE_TO_BLUEPRINT_ROLE.get(db_role, BlueprintRole.NONE)


def is_governance_reviewer(db_role: str) -> bool:
    return blueprint_role_for(db_role) == BlueprintRole.GOVERNANCE_REVIEWER


def is_intake_specialist(db_role: str) -> bool:
    return blueprint_role_for(db_role) == BlueprintRole.INTAKE_SPECIALIST


def is_administrator(db_role: str) -> bool:
    return blueprint_role_for(db_role) == BlueprintRole.ADMINISTRATOR


def can_claim_review(db_role: str) -> bool:
    """
    Governance Reviewers may claim a packet for review (DEC000001 §5.3).

    NOT CURRENTLY CALLED (see can_administer_override's docstring below for
    why): operations.claim_intake_packet (supabase/migrations/018_intake_
    claim_release_rpcs.sql) is the live authorization source for claim, and
    the task #43 correction deliberately widened it to also permit
    Administrator authority to claim, not Governance Reviewers alone. This
    narrow helper checks only is_governance_reviewer and does not reflect
    that widening; do not read it as the live source of truth for
    intake.review.claim's authorization.
    """
    return is_governance_reviewer(db_role)


def can_administer_override(db_role: str) -> bool:
    """
    Only Administrators may perform an authorized override of an otherwise
    claimant-only decision. Kept as one shared function so "who may override"
    is answered in exactly one place; individual commands decide separately
    *whether* an override is authorized for them at all (see
    can_override_release / can_override_approve below).

    NOT CURRENTLY CALLED: operations.claim_intake_packet /
    operations.release_intake_packet / operations.approve_intake_packet /
    operations.return_intake_packet (supabase/migrations/017_intake_review_
    decision_rpcs.sql, 018_intake_claim_release_rpcs.sql) perform their own
    direct operations.users.role lookup rather than calling into this
    module — the RPC-is-authoritative design from the task #43/#44
    correction (see those migrations' "Role-check duplication" comments).
    This module is retained for any future non-RPC caller but is presently
    dead code on the claim/release/approve/return request path; do not read
    it as the live source of truth for those four commands' authorization.

    Return override, historically absent here: as of the Founder/CEO
    governance clarification (2026-07-16), intake.review.return DOES permit
    an Administrator override (DEC000001 §5.5, migration 017) — this was
    previously the one command with no override path at all. No
    can_override_return function was added to this module for it, since
    return's authorization now lives entirely in the RPC per the note
    above, not here.
    """
    return is_administrator(db_role)


def can_override_release(db_role: str) -> bool:
    """Only Administrators may release a packet claimed by someone else (DEC000001 §5.5)."""
    return can_administer_override(db_role)


def can_override_approve(db_role: str) -> bool:
    """
    Only Administrators may approve a packet claimed by someone else.

    Authorized explicitly by DEC000001 §3's command table: "Requires source
    state in_review, claimant-or-admin only" for intake.review.approve
    (CMD000005). Do not reuse this function for return: not because return
    lacks an override (it now has one — see can_administer_override's
    docstring above, and DEC000001 §5.5, corrected 2026-07-16), but because
    return's authorization is enforced entirely inside
    operations.return_intake_packet (migration 017), not via this module.
    """
    return can_administer_override(db_role)
