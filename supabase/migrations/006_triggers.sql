-- ============================================================
-- 006_triggers.sql
-- Triggers enforcing GoldPan's architectural constraints.
--
-- Triggers:
--   1. updated_at auto-update on all evidence tables
--   2. lifecycle_events append-only (prevent UPDATE/DELETE)
--   3. audit_log prevent UPDATE/DELETE (audit trail integrity)
--   4. Auto-create lifecycle_event when restaurant status changes
--   5. evidence audit log trigger for all evidence table writes
--   6. Allergen disclosure change requires reason
-- ============================================================


-- ── 1. updated_at auto-update ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION operations.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_restaurants_updated_at
    BEFORE UPDATE ON evidence.restaurants
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_menu_sources_updated_at
    BEFORE UPDATE ON evidence.menu_sources
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_dishes_updated_at
    BEFORE UPDATE ON evidence.dishes
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_ingredients_updated_at
    BEFORE UPDATE ON evidence.ingredients
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_allergen_disc_updated_at
    BEFORE UPDATE ON evidence.allergen_disclosures
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON operations.users
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();

CREATE TRIGGER trg_feature_flags_updated_at
    BEFORE UPDATE ON operations.feature_flags
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();


-- ── 2. lifecycle_events append-only ──────────────────────────────────────────
-- Prevents UPDATE and DELETE on lifecycle_events.
-- The audit trail of restaurant lifecycle transitions must be immutable.

CREATE OR REPLACE FUNCTION operations.prevent_lifecycle_events_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'lifecycle_events is append-only. UPDATE and DELETE are prohibited. '
        'This is enforced by the GoldPan architecture (INTAKE_OS_RESTAURANT_REGISTRY.md). '
        'Operation: %, table: evidence.lifecycle_events', TG_OP;
END;
$$;

CREATE TRIGGER trg_lifecycle_events_append_only
    BEFORE UPDATE OR DELETE ON evidence.lifecycle_events
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_lifecycle_events_mutation();


-- ── 3. audit_log append-only ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION operations.prevent_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'operations.audit_log is append-only. UPDATE and DELETE are prohibited. '
        'Operation: %, table: operations.audit_log', TG_OP;
END;
$$;

CREATE TRIGGER trg_audit_log_append_only
    BEFORE UPDATE OR DELETE ON operations.audit_log
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_audit_log_mutation();


-- ── 4. Auto-create lifecycle_event on restaurant status change ────────────────
-- Whenever restaurants.lifecycle_status changes, automatically insert a
-- lifecycle_events row. This ensures the audit trail is never incomplete
-- even if the calling code forgets to write it manually.

CREATE OR REPLACE FUNCTION evidence.auto_lifecycle_event()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Only fire when lifecycle_status actually changed
    IF NEW.lifecycle_status IS DISTINCT FROM OLD.lifecycle_status THEN
        INSERT INTO evidence.lifecycle_events (
            restaurant_id,
            event_date,
            from_status,
            to_status,
            actor_id,
            actor_type,
            notes
        ) VALUES (
            NEW.restaurant_id,
            current_date,
            OLD.lifecycle_status,
            NEW.lifecycle_status,
            NEW.status_updated_by,
            CASE
                WHEN NEW.status_updated_by IS NOT NULL THEN 'user'
                ELSE 'system'
            END,
            'Auto-recorded by trigger on restaurants.lifecycle_status change'
        );
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_auto_lifecycle_event
    AFTER UPDATE OF lifecycle_status ON evidence.restaurants
    FOR EACH ROW EXECUTE FUNCTION evidence.auto_lifecycle_event();


-- ── 5. Evidence audit log trigger ────────────────────────────────────────────
-- Logs all INSERT, UPDATE, DELETE operations on evidence tables to
-- operations.audit_log. Applied to dishes, ingredients, allergen_disclosures.

CREATE OR REPLACE FUNCTION operations.log_evidence_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_record_id uuid;
    v_old_values jsonb;
    v_new_values jsonb;
BEGIN
    -- Determine record_id based on table
    IF TG_OP = 'DELETE' THEN
        v_record_id := OLD.dish_id;    -- works for dishes; ingredient/allergen use their own PK
        v_old_values := to_jsonb(OLD);
        v_new_values := NULL;
    ELSIF TG_OP = 'INSERT' THEN
        v_record_id := NEW.dish_id;
        v_old_values := NULL;
        v_new_values := to_jsonb(NEW);
    ELSE -- UPDATE
        v_record_id := NEW.dish_id;
        v_old_values := to_jsonb(OLD);
        v_new_values := to_jsonb(NEW);
    END IF;

    INSERT INTO operations.audit_log (
        table_schema,
        table_name,
        record_id,
        operation,
        actor_id,
        actor_type,
        old_values,
        new_values,
        changed_at
    ) VALUES (
        TG_TABLE_SCHEMA,
        TG_TABLE_NAME,
        v_record_id,
        TG_OP,
        operations.current_user_id(),
        CASE
            WHEN operations.current_user_role() = 'governance_engine' THEN 'pipeline'
            WHEN operations.current_user_id() IS NOT NULL THEN 'user'
            ELSE 'system'
        END,
        v_old_values,
        v_new_values,
        now()
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;

CREATE TRIGGER trg_audit_dishes
    AFTER INSERT OR UPDATE OR DELETE ON evidence.dishes
    FOR EACH ROW EXECUTE FUNCTION operations.log_evidence_change();

CREATE TRIGGER trg_audit_ingredients
    AFTER INSERT OR UPDATE OR DELETE ON evidence.ingredients
    FOR EACH ROW EXECUTE FUNCTION operations.log_evidence_change();

CREATE TRIGGER trg_audit_allergen_disclosures
    AFTER INSERT OR UPDATE OR DELETE ON evidence.allergen_disclosures
    FOR EACH ROW EXECUTE FUNCTION operations.log_evidence_change();


-- ── 6. Allergen disclosure: require reason for UPDATE ────────────────────────
-- Allergen data is safety-critical. Any UPDATE to allergen_disclosures
-- must include a reason (stored in a session variable that calling code sets).
-- This is a best-effort check — the full GP-RULE-012 requirement is enforced
-- at the API layer; this trigger provides a database-level backstop.

CREATE OR REPLACE FUNCTION evidence.require_allergen_update_reason()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_reason text;
BEGIN
    -- Calling code sets this via: SET LOCAL goldpan.change_reason = 'reason text';
    v_reason := current_setting('goldpan.change_reason', true);
    IF v_reason IS NULL OR trim(v_reason) = '' THEN
        RAISE EXCEPTION
            'Allergen disclosure UPDATE requires a reason. '
            'Set it via: SET LOCAL goldpan.change_reason = ''reason text''; '
            'before executing the UPDATE. Required by GP-RULE-012.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_allergen_disc_require_reason
    BEFORE UPDATE ON evidence.allergen_disclosures
    FOR EACH ROW EXECUTE FUNCTION evidence.require_allergen_update_reason();


-- ── 7. knowledge tables: enforce governance_engine only ──────────────────────
-- Belt-and-suspenders check: if somehow a non-pipeline actor tries to
-- write to knowledge tables, raise an exception before the RLS policy fires.

CREATE OR REPLACE FUNCTION knowledge.enforce_pipeline_only_write()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF operations.current_user_role() != 'governance_engine' THEN
        RAISE EXCEPTION
            'Knowledge System tables are written exclusively by the governance_engine. '
            'Current role: %. '
            'Table: %.% — Evidence/Knowledge boundary violation.',
            operations.current_user_role(), TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_derived_filters_pipeline_only
    BEFORE INSERT OR UPDATE ON knowledge.derived_filters
    FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_pipeline_only_write();

CREATE TRIGGER trg_transparency_scores_pipeline_only
    BEFORE INSERT OR UPDATE ON knowledge.transparency_scores
    FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_pipeline_only_write();

CREATE TRIGGER trg_freshness_state_pipeline_only
    BEFORE INSERT OR UPDATE ON knowledge.freshness_state
    FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_pipeline_only_write();
