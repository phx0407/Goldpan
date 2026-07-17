-- ============================================================
-- 011_submission_tables.sql
-- External input layer — partner and restaurant update submissions
--
-- Tables:
--   operations.partner_submissions            — general partner-initiated contact
--   operations.restaurant_update_submissions  — restaurant data update requests
--
-- Architectural boundary (MUST NOT be crossed):
--   Submissions are EVIDENCE CANDIDATES only.
--   They NEVER write to evidence.* tables directly.
--   A human reviewer must approve and trigger an Intake session or
--   make a deliberate evidence edit. The review audit trail is in
--   this table (reviewed_by, reviewed_at, resulting_intake_session).
--
-- Two paths:
--   1. INTERNAL INTERACTION INPUT
--      GoldPan team enters calls, emails, meetings, notes →
--      writes to operations.partner_actions (migration 010).
--      This is already live.
--
--   2. FUTURE RESTAURANT PORTAL / EXTERNAL SUBMISSION
--      Restaurants or partners submit updates via a portal or email form.
--      All submissions land here with status = 'pending_review'.
--      A coordinator reviews and either approves (triggering intake/edit)
--      or returns/rejects with a reason.
--
-- Submission types for restaurant_update_submissions:
--   menu_update            — new dishes, removed dishes, section changes
--   ingredient_correction  — ingredient list change for a specific dish
--   calorie_update         — calorie value for a dish
--   allergen_update        — allergen disclosure changes
--   nutrition_doc_upload   — full PDF (allergen guide, nutrition facts)
--   claim_submission       — new restaurant-level claim (vegan-friendly, etc.)
--   contact_update         — owner/manager contact info
--   restaurant_info_update — hours, website, address, location
--   correction_request     — general "this is wrong, please fix" submission
--   other
--
-- Submission types for partner_submissions:
--   partnership_interest   — restaurant/org wants to partner
--   contact_update         — update their own contact info
--   meeting_request        — request a call or meeting
--   general_inquiry        — open-ended message
--   portal_signup          — registered via future partner portal
--   other
-- ============================================================


-- ── operations.partner_submissions ───────────────────────────────────────────
-- General partner-initiated contact or submissions.
-- Used for future portal, email forms, or any external-facing intake.

CREATE TABLE IF NOT EXISTS operations.partner_submissions (
    submission_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source linkage (nullable — may arrive before a CRM record exists)
    partner_id          uuid        REFERENCES operations.partners(partner_id)
                                    ON DELETE SET NULL,
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id)
                                    ON DELETE SET NULL,

    -- Submitter identity (self-reported; not authenticated)
    submitted_by_name   text,
    submitted_by_email  text,
    submitted_by_phone  text,
    submitted_by_role   text,       -- 'owner', 'manager', 'dietitian', 'pr_agency', etc.
    organization_name   text,       -- organization name if not yet a CRM partner

    -- Submission content
    submission_type     text        NOT NULL
                        CHECK (submission_type IN (
                            'partnership_interest',
                            'contact_update',
                            'meeting_request',
                            'general_inquiry',
                            'portal_signup',
                            'other'
                        )),
    message             text,       -- free-form message from submitter
    payload_json        jsonb,      -- structured form data for programmatic submissions

    -- Review workflow
    status              text        NOT NULL DEFAULT 'pending_review'
                        CHECK (status IN (
                            'pending_review',
                            'in_review',
                            'approved',
                            'returned',         -- sent back to submitter for more info
                            'rejected',
                            'converted'         -- converted to partner_actions or CRM record
                        )),
    reviewed_by         text,
    reviewed_at         timestamptz,
    review_notes        text,       -- internal reviewer notes (never sent to submitter)
    return_message      text,       -- message sent back to submitter if returned

    -- After conversion: what was created
    converted_action_id uuid        REFERENCES operations.partner_actions(action_id)
                                    ON DELETE SET NULL,
    converted_partner_id uuid       REFERENCES operations.partners(partner_id)
                                    ON DELETE SET NULL,

    -- Source tracking
    source              text        DEFAULT 'portal'
                        CHECK (source IN ('portal', 'email_form', 'internal', 'api', 'other')),
    ip_hash             text,       -- SHA-256 of submitter IP, never raw

    -- Meta
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.partner_submissions IS
    'General partner-initiated submissions: partnership interest, contact updates, '
    'meeting requests, general inquiries. Landing table for future portal forms. '
    'Requires human review before any CRM action is taken.';

COMMENT ON COLUMN operations.partner_submissions.payload_json IS
    'Structured form payload for programmatic submissions. Schema varies by submission_type. '
    'Not validated by DB — validated by API layer.';

COMMENT ON COLUMN operations.partner_submissions.status IS
    'pending_review → in_review → approved/returned/rejected/converted. '
    'Only the reviewing coordinator advances status.';


-- Trigger: auto-update updated_at
DROP TRIGGER IF EXISTS trg_partner_submissions_updated_at ON operations.partner_submissions;
CREATE TRIGGER trg_partner_submissions_updated_at
    BEFORE UPDATE ON operations.partner_submissions
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_psub_partner    ON operations.partner_submissions(partner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_psub_status     ON operations.partner_submissions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_psub_type       ON operations.partner_submissions(submission_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_psub_email      ON operations.partner_submissions(submitted_by_email);
CREATE INDEX IF NOT EXISTS idx_psub_created    ON operations.partner_submissions(created_at DESC);


-- ── operations.restaurant_update_submissions ──────────────────────────────────
-- Restaurant-submitted data updates: menu changes, ingredient corrections,
-- calorie/allergen/nutrition updates, restaurant info corrections.
--
-- BOUNDARY: These are EVIDENCE CANDIDATES.
-- They MUST NOT be applied to evidence.* tables without human review.
-- Approval → reviewer triggers an Intake session or deliberate evidence edit.

CREATE TABLE IF NOT EXISTS operations.restaurant_update_submissions (
    submission_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source linkage
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id)
                                    ON DELETE SET NULL,
    partner_id          uuid        REFERENCES operations.partners(partner_id)
                                    ON DELETE SET NULL,

    -- Submitter identity (self-reported)
    submitted_by_name   text,
    submitted_by_email  text,
    submitted_by_phone  text,
    submitted_by_role   text,       -- 'owner', 'manager', 'head_chef', 'dietitian', 'pr_agency'

    -- Submission classification
    submission_type     text        NOT NULL
                        CHECK (submission_type IN (
                            'menu_update',
                            'ingredient_correction',
                            'calorie_update',
                            'allergen_update',
                            'nutrition_doc_upload',
                            'claim_submission',
                            'contact_update',
                            'restaurant_info_update',
                            'correction_request',
                            'other'
                        )),

    -- Content
    description         text,       -- human-written description of what changed and why
    payload_json        jsonb,      -- structured submission (schema varies by submission_type)

    -- Item-level reference (for dish/ingredient submissions)
    dish_id             uuid        REFERENCES evidence.dishes(dish_id)
                                    ON DELETE SET NULL,
    dish_name           text,       -- denormalized, for when dish_id is unknown

    -- Attachment (for nutrition guides, PDFs, etc.)
    attachment_url      text,       -- URL to uploaded document (Supabase storage or S3)
    attachment_filename text,
    attachment_type     text        -- 'menu_pdf', 'allergen_guide', 'nutrition_facts', 'image', 'other'
                        CHECK (attachment_type IN (
                            'menu_pdf', 'allergen_guide', 'nutrition_facts',
                            'ingredient_list', 'image', 'other'
                        ) OR attachment_type IS NULL),

    -- Submitter confidence / context
    verification_note   text,       -- submitter-provided context: "this is from our current menu as of June 2026"
    effective_date      date,       -- when the change takes effect, if provided

    -- ── Review workflow ────────────────────────────────────────────────────────
    -- CRITICAL: status gates all downstream evidence changes.
    -- Nothing in evidence.* may be altered because of this submission
    -- until status = 'approved' and a reviewer has taken deliberate action.

    status              text        NOT NULL DEFAULT 'pending_review'
                        CHECK (status IN (
                            'pending_review',   -- just arrived, nobody has looked
                            'in_review',        -- coordinator is actively reviewing
                            'approved',         -- coordinator approved; action taken or queued
                            'returned',         -- coordinator sent it back for more info
                            'rejected'          -- not actionable, spam, or policy violation
                        )),
    priority            text        NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('urgent', 'normal', 'low')),
    reviewed_by         text,               -- GoldPan coordinator who reviewed
    reviewed_at         timestamptz,
    review_notes        text,               -- internal reviewer notes
    return_reason       text,               -- reason sent back to submitter if returned

    -- ── Post-approval outcome (filled after approval) ─────────────────────────
    -- After approval, the coordinator either:
    --   (a) manually triggers an Intake session (records session ID here), OR
    --   (b) directly edits evidence records (records a JSON summary here)
    -- This field is the audit trail of what changed downstream.

    resulting_intake_session    text,   -- intake_session_id if approval triggered Intake
    resulting_evidence_summary  jsonb,  -- summary of evidence records created/updated

    -- Source tracking
    source              text        NOT NULL DEFAULT 'portal'
                        CHECK (source IN ('portal', 'email', 'internal_import', 'api', 'other')),
    ip_hash             text,

    -- Meta
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.restaurant_update_submissions IS
    'Restaurant-submitted data updates: menu changes, ingredient corrections, '
    'allergen/calorie/nutrition updates, correction requests. '
    'EVIDENCE BOUNDARY: nothing here touches evidence.* until a coordinator '
    'approves and deliberately triggers Intake or an evidence edit. '
    'Append-only for the submission row; only status and review fields are mutable.';

COMMENT ON COLUMN operations.restaurant_update_submissions.status IS
    'Gate for the evidence boundary. Only coordinators advance status. '
    'pending_review → in_review → approved / returned / rejected. '
    'approved does NOT automatically write to evidence — reviewer must take '
    'deliberate action (trigger Intake session or direct edit).';

COMMENT ON COLUMN operations.restaurant_update_submissions.payload_json IS
    'Structured payload — schema varies by submission_type. Examples: '
    '{"dish_name":"Avocado Toast","old_ingredients":["egg"],"new_ingredients":["no egg"]} '
    'for ingredient_correction; {"old_calories":"450","new_calories":"380"} '
    'for calorie_update. Validated by API layer, not DB.';

COMMENT ON COLUMN operations.restaurant_update_submissions.resulting_evidence_summary IS
    'Filled by reviewer after approval. Records what evidence records were '
    'created or updated as a result of this submission. Audit trail.';


-- Trigger: auto-update updated_at
DROP TRIGGER IF EXISTS trg_restupdsub_updated_at ON operations.restaurant_update_submissions;
CREATE TRIGGER trg_restupdsub_updated_at
    BEFORE UPDATE ON operations.restaurant_update_submissions
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rusub_restaurant ON operations.restaurant_update_submissions(restaurant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rusub_partner    ON operations.restaurant_update_submissions(partner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rusub_status     ON operations.restaurant_update_submissions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rusub_type       ON operations.restaurant_update_submissions(submission_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rusub_priority   ON operations.restaurant_update_submissions(priority, status);
CREATE INDEX IF NOT EXISTS idx_rusub_dish       ON operations.restaurant_update_submissions(dish_id);
CREATE INDEX IF NOT EXISTS idx_rusub_created    ON operations.restaurant_update_submissions(created_at DESC);


-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE operations.partner_submissions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.restaurant_update_submissions ENABLE ROW LEVEL SECURITY;

-- partner_submissions: coordinators and admins read/write
DROP POLICY IF EXISTS "partner_submissions_select" ON operations.partner_submissions;
CREATE POLICY "partner_submissions_select" ON operations.partner_submissions FOR SELECT
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS "partner_submissions_insert" ON operations.partner_submissions;
CREATE POLICY "partner_submissions_insert" ON operations.partner_submissions FOR INSERT
    WITH CHECK (
        -- service_role for API writes (future portal) OR internal team
        current_user IN ('postgres', 'service_role')
        OR operations.current_user_role() IN ('coordinator', 'admin')
    );

DROP POLICY IF EXISTS "partner_submissions_update" ON operations.partner_submissions;
CREATE POLICY "partner_submissions_update" ON operations.partner_submissions FOR UPDATE
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

-- restaurant_update_submissions: same pattern
DROP POLICY IF EXISTS "rusub_select" ON operations.restaurant_update_submissions;
CREATE POLICY "rusub_select" ON operations.restaurant_update_submissions FOR SELECT
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS "rusub_insert" ON operations.restaurant_update_submissions;
CREATE POLICY "rusub_insert" ON operations.restaurant_update_submissions FOR INSERT
    WITH CHECK (
        current_user IN ('postgres', 'service_role')
        OR operations.current_user_role() IN ('coordinator', 'admin')
    );

DROP POLICY IF EXISTS "rusub_update" ON operations.restaurant_update_submissions;
CREATE POLICY "rusub_update" ON operations.restaurant_update_submissions FOR UPDATE
    USING (
        -- Only coordinators/admins may advance review status
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );


-- ── Grants ────────────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE ON operations.partner_submissions           TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE ON operations.restaurant_update_submissions TO service_role, authenticated;
