-- ============================================================
-- 015_intake_packets.sql
-- Intake OS — intake packet queue table.
--
-- An intake packet is the structured output of one canvassing run
-- against one restaurant (produced by intake_agent.py).  This table
-- persists packets so the Intake OS web UI can display the queue,
-- allow human review, and trigger ingestion.
--
-- Lifecycle (packet_status):
--   pending_review  → packet submitted, awaiting human review
--   returned        → reviewer returned packet to canvasser with notes
--   approved        → human reviewer approved the evidence
--   ingested        → ingest_packet.py --commit ran successfully
--
-- JSON packet structure is preserved in packet_data (JSONB) for full
-- fidelity.  Top-level summary fields (dish_count, etc.) are extracted
-- for querying without parsing JSON.
--
-- Idempotency: uses a UNIQUE constraint on
--   (restaurant_id, canvass_date, packet_status_at_submit)
-- to prevent duplicate submissions of the same canvassing run.
-- ============================================================

-- ── operations.intake_packets ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS operations.intake_packets (
    packet_id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Restaurant identity (restaurant_id may be NULL for new restaurants
    -- not yet in the DB; restaurant_external_id always set)
    restaurant_id           uuid        REFERENCES evidence.restaurants(restaurant_id)
                                        ON DELETE SET NULL,
    restaurant_external_id  text        NOT NULL,
    restaurant_name         text        NOT NULL,

    -- Packet lifecycle
    packet_status           text        NOT NULL DEFAULT 'pending_review'
                            CHECK (packet_status IN (
                                'pending_review', 'returned', 'approved', 'ingested'
                            )),

    -- Provenance
    canvass_date            date        NOT NULL,
    source_urls             text[]      NOT NULL DEFAULT '{}',
    agent_version           text,
    model_used              text,
    processing_time_ms      int,

    -- Evidence summary (extracted from packet for querying)
    dish_count              int         NOT NULL DEFAULT 0,
    review_flag_count       int         NOT NULL DEFAULT 0,
    evidence_score_overall  int,        -- 0-100 composite
    evidence_score_detail   jsonb,      -- full evidence_score object

    -- Full packet payload (for detail view and ingest)
    packet_data             jsonb       NOT NULL,

    -- Review workflow
    reviewer_notes          text,
    return_reason           text,
    submitted_at            timestamptz NOT NULL DEFAULT now(),
    reviewed_at             timestamptz,
    reviewed_by             text,
    ingested_at             timestamptz,

    -- Prevent duplicate submissions of the same canvassing run
    UNIQUE (restaurant_external_id, canvass_date)
);

COMMENT ON TABLE operations.intake_packets IS
    'Intake packet queue. One row per canvassing run. Managed by Intake OS web UI and ingest_packet.py.';
COMMENT ON COLUMN operations.intake_packets.packet_data IS
    'Full JSON packet as produced by intake_agent.py. Includes dishes, review_flags, agent_metadata, evidence_score.';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_intake_packets_status
    ON operations.intake_packets(packet_status, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_intake_packets_restaurant
    ON operations.intake_packets(restaurant_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_intake_packets_restaurant_ext
    ON operations.intake_packets(restaurant_external_id);

-- ── RLS: admin role only ─────────────────────────────────────────────────────
ALTER TABLE operations.intake_packets ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS — scripts and API use service role.
-- No anon or authenticated policies: Intake OS is admin-only.
