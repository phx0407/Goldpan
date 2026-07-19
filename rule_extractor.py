#!/usr/bin/env python3
"""
GoldPan™ Rule Learning Extractor v1.0.0

Scans *_corrections.json files, groups corrections by (domain, rule_type, trigger_key),
and maintains candidate_rules.json for human review and approval.

Reusable across all GoldPan™ operating systems:

  python rule_extractor.py --domain intake
  python rule_extractor.py --domain biz_dev
  python rule_extractor.py --domain all
  python rule_extractor.py --domain intake --dry-run

This extractor NEVER modifies any Standard document.
All candidate rules require human approval before taking effect.

Schema: docs/CORRECTIONS_SCHEMA.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "1.0.0"

# ── Default paths ───────────────────────────────────────────────────────────────
GOLDPAN_ROOT         = Path(__file__).parent
INTAKE_PACKETS_DIR   = GOLDPAN_ROOT / "intake_packets"
CANDIDATE_RULES_FILE = GOLDPAN_ROOT / "candidate_rules.json"

# ── Promotion thresholds ────────────────────────────────────────────────────────
STANDARD_MIN_RESTAURANTS  = 2   # Independent restaurants needed for standard rules
SAFETY_CRITICAL_THRESHOLD = 1   # One confirmed occurrence for safety-critical rules

# ── Enums ───────────────────────────────────────────────────────────────────────
VALID_DOMAINS = frozenset({
    "intake",
    "biz_dev",
    "customer_support",
    "operations",
})

VALID_RULE_TYPES = frozenset({
    "verbatim_component_trigger",
    "allergen_flag_constraint",
    "ingredient_classification",
    "section_propagation",
    "consistency_rule",
    "flag_batching",
})

VALID_PROMOTION_STATUSES = frozenset({
    "draft",
    "ready_for_review",
    "approved",
    "rejected",
    "merged",
})

# Terminal statuses — the extractor never modifies these
TERMINAL_STATUSES = frozenset({"approved", "rejected", "merged"})

# Status rank — used to enforce no-downgrade rule
STATUS_RANK: dict[str, int] = {
    "draft": 0,
    "ready_for_review": 1,
    "approved": 2,
    "rejected": 2,
    "merged": 3,
}

# Domain → ID prefix mapping (extensible)
DOMAIN_PREFIXES: dict[str, str] = {
    "intake":           "INTAKE",
    "biz_dev":          "BIZ",
    "customer_support": "CS",
    "operations":       "OPS",
}


# ══════════════════════════════════════════════════════════════════════════════
# RuleLearningExtractor
# ══════════════════════════════════════════════════════════════════════════════

class RuleLearningExtractor:
    """
    Domain-agnostic rule learning extractor.

    For each *_corrections.json file found under packets_dir:
      1. Load and validate the file.
      2. Filter to the target domain (or accept all if domain='all').
      3. Group corrections by (domain, rule_type, trigger_key).
      4. For each group, create a new candidate rule or update an existing one.
      5. Apply promotion thresholds.
      6. Write the updated candidate_rules.json without overwriting history.

    Design principles:
      - Idempotent: running twice on the same inputs produces the same output.
      - Additive: never removes evidence, never resets counts.
      - Non-destructive: never modifies proposed_rule_text once set.
      - No-downgrade: promotion_status only moves forward.
    """

    def __init__(
        self,
        domain: str,
        packets_dir: Path,
        output_file: Path,
        dry_run: bool = False,
    ):
        if domain != "all" and domain not in VALID_DOMAINS:
            sys.exit(
                f"Error: Unknown domain '{domain}'.\n"
                f"Valid values: {sorted(VALID_DOMAINS)} or 'all'"
            )
        self.domain      = domain
        self.packets_dir = packets_dir
        self.output_file = output_file
        self.dry_run     = dry_run
        self.run_ts      = datetime.now(timezone.utc).isoformat()

    # ── File scanning ──────────────────────────────────────────────────────────

    def scan_correction_files(self) -> list[Path]:
        """Return all *_corrections.json paths found recursively under packets_dir."""
        if not self.packets_dir.exists():
            sys.exit(f"Error: Packets directory not found: {self.packets_dir}")
        return sorted(self.packets_dir.rglob("*_corrections.json"))

    def load_correction_file(self, path: Path) -> dict | None:
        """
        Load and validate one corrections file.
        Returns parsed dict or None if the file cannot be used.
        Validation is intentionally lenient — warn on bad files, never crash.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  ⚠  Skipping {path.name}: {exc}")
            return None

        required_top = {"domain", "packet_ref", "restaurant_name", "review_date", "corrections"}
        missing = required_top - set(data.keys())
        if missing:
            print(f"  ⚠  Skipping {path.name}: missing top-level field(s): {sorted(missing)}")
            return None

        if not isinstance(data.get("corrections"), list):
            print(f"  ⚠  Skipping {path.name}: 'corrections' must be a list")
            return None

        return data

    def filter_by_domain(self, files: list[dict]) -> list[dict]:
        """Keep only files matching the target domain (pass-through if domain='all')."""
        if self.domain == "all":
            return files
        return [f for f in files if f.get("domain") == self.domain]

    # ── Grouping ───────────────────────────────────────────────────────────────

    @staticmethod
    def group_key(domain: str, rule_type: str, trigger_key: str) -> str:
        """
        Canonical string key used to match corrections across files.
        Format: 'domain|rule_type|trigger_key'
        """
        return f"{domain}|{rule_type}|{trigger_key}"

    def group_corrections(self, files: list[dict]) -> dict[str, list[dict]]:
        """
        Build a map from group_key → list of enriched corrections.

        Each correction in the list carries '_domain', '_restaurant',
        '_packet_ref', and '_review_date' fields from its parent file,
        enabling provenance tracking without modifying the original schema.
        """
        groups: dict[str, list[dict]] = {}

        for file_data in files:
            domain       = file_data["domain"]
            restaurant   = file_data["restaurant_name"]
            packet_ref   = file_data["packet_ref"]
            review_date  = file_data["review_date"]

            for correction in file_data["corrections"]:
                rule_type   = correction.get("rule_type", "").strip()
                trigger_key = correction.get("trigger_key", "").strip()
                cid         = correction.get("correction_id", "?")

                if not rule_type:
                    print(f"  ⚠  Correction {cid} in {packet_ref}: missing rule_type — skipping")
                    continue
                if not trigger_key:
                    print(f"  ⚠  Correction {cid} in {packet_ref}: missing trigger_key — skipping")
                    continue

                key = self.group_key(domain, rule_type, trigger_key)
                groups.setdefault(key, [])

                enriched = {
                    **correction,
                    "_domain":     domain,
                    "_restaurant": restaurant,
                    "_packet_ref": packet_ref,
                    "_review_date": review_date,
                }
                groups[key].append(enriched)

        return groups

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def unique_restaurants(group: list[dict]) -> list[str]:
        """Ordered deduplicated list of restaurants in a correction group."""
        seen: set[str] = set()
        result: list[str] = []
        for c in group:
            r = c["_restaurant"]
            if r not in seen:
                seen.add(r)
                result.append(r)
        return result

    @staticmethod
    def is_safety_critical(group: list[dict]) -> bool:
        """True if any correction in the group is safety-critical."""
        return any(c.get("safety_critical", False) for c in group)

    # ── Promotion ──────────────────────────────────────────────────────────────

    def evaluate_status(
        self,
        safety_critical: bool,
        times_observed: int,
        restaurants_observed: list[str],
        current_status: str,
    ) -> str:
        """
        Compute the correct promotion_status given current evidence.
        Never downgrades: if new_status rank < current_status rank, return current.
        Terminal statuses (approved, rejected, merged) are always preserved.
        """
        if current_status in TERMINAL_STATUSES:
            return current_status

        if safety_critical and times_observed >= SAFETY_CRITICAL_THRESHOLD:
            new_status = "ready_for_review"
        elif not safety_critical and len(restaurants_observed) >= STANDARD_MIN_RESTAURANTS:
            new_status = "ready_for_review"
        else:
            new_status = "draft"

        # No-downgrade guard
        if STATUS_RANK.get(new_status, 0) < STATUS_RANK.get(current_status, 0):
            return current_status
        return new_status

    # ── Evidence builders ──────────────────────────────────────────────────────

    @staticmethod
    def _evidence_key(item: dict) -> str:
        return f"{item.get('packet_ref', '')}|{item.get('dish', '')}|{item.get('menu_text', '')}"

    @staticmethod
    def _output_key(output: dict) -> str:
        """Dedup key for wrong/correct outputs — excludes provenance fields."""
        clean = {k: v for k, v in output.items() if not k.startswith("_")}
        return json.dumps(clean, sort_keys=True, ensure_ascii=False)

    def build_evidence(self, group: list[dict]) -> list[dict]:
        """Deduplicated evidence items from the correction group."""
        seen: set[str] = set()
        result: list[dict] = []
        for c in group:
            item = {
                "packet_ref":    c["_packet_ref"],
                "restaurant":    c["_restaurant"],
                "dish":          c.get("dish", ""),
                "menu_text":     c.get("menu_text", ""),
                "correction_id": c.get("correction_id", ""),
                "review_date":   c["_review_date"],
            }
            key = self._evidence_key(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def build_wrong_outputs(self, group: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for c in group:
            raw = c.get("wrong_output")
            if not raw:
                continue
            key = self._output_key(raw)
            if key not in seen:
                seen.add(key)
                result.append({**raw, "_from": c["_packet_ref"]})
        return result

    def build_correct_outputs(self, group: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for c in group:
            raw = c.get("correct_output")
            if not raw:
                continue
            key = self._output_key(raw)
            if key not in seen:
                seen.add(key)
                result.append({**raw, "_from": c["_packet_ref"]})
        return result

    def collect_draft_texts(self, group: list[dict]) -> list[str]:
        """Unique non-empty proposed_rule_text_draft values from the group."""
        seen: set[str] = set()
        result: list[str] = []
        for c in group:
            text = c.get("proposed_rule_text_draft", "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    # ── Rule ID generation ─────────────────────────────────────────────────────

    def domain_prefix(self, domain: str) -> str:
        return DOMAIN_PREFIXES.get(domain, domain.upper()[:6])

    def next_rule_id(self, existing_rules: list[dict], domain: str) -> str:
        """Sequential rule ID for the domain: INTAKE-R001, BIZ-R002, etc."""
        prefix = self.domain_prefix(domain)
        nums: list[int] = []
        for rule in existing_rules:
            if rule.get("domain") != domain:
                continue
            rid = rule.get("candidate_rule_id", "")
            # Extract trailing digits after the last 'R'
            parts = rid.rsplit("R", 1)
            if len(parts) == 2 and parts[1].isdigit():
                nums.append(int(parts[1]))
        n = max(nums, default=0) + 1
        return f"{prefix}-R{n:03d}"

    # ── Rule create / update ───────────────────────────────────────────────────

    def create_rule(self, group: list[dict], existing_rules: list[dict]) -> dict:
        """Build a new candidate rule from a correction group."""
        first       = group[0]
        domain      = first["_domain"]
        rule_type   = first.get("rule_type", "")
        trigger_key = first.get("trigger_key", "")
        restaurants = self.unique_restaurants(group)
        safety      = self.is_safety_critical(group)
        evidence    = self.build_evidence(group)
        drafts      = self.collect_draft_texts(group)

        status = self.evaluate_status(safety, len(evidence), restaurants, "draft")

        return {
            "candidate_rule_id":  self.next_rule_id(existing_rules, domain),
            "domain":             domain,
            "rule_type":          rule_type,
            "trigger_key":        trigger_key,
            "trigger_pattern":    first.get("trigger_pattern", trigger_key.replace("_", " ")),
            # proposed_rule_text is set from the first draft on creation only.
            # The extractor never overwrites it after creation — it is the human's domain.
            "proposed_rule_text": drafts[0] if drafts else "",
            # draft_texts accumulates all reviewer drafts as reference material.
            "draft_texts":        drafts,
            "target_section":     first.get("target_section", ""),
            "safety_critical":    safety,
            "evidence":           evidence,
            "wrong_outputs":      self.build_wrong_outputs(group),
            "correct_outputs":    self.build_correct_outputs(group),
            "times_observed":     len(evidence),
            "restaurants_observed": restaurants,
            "promotion_status":   status,
            "promoted_at":        self.run_ts if status == "ready_for_review" else None,
            "approved_at":        None,
            "merged_at":          None,
            "created_at":         self.run_ts,
            "last_updated_at":    self.run_ts,
        }

    def update_rule(self, rule: dict, group: list[dict]) -> dict:
        """
        Merge new corrections into an existing candidate rule.

        What the extractor WILL update:
          evidence, wrong_outputs, correct_outputs, draft_texts,
          times_observed, restaurants_observed, safety_critical,
          promotion_status, promoted_at, last_updated_at

        What the extractor will NOT touch:
          proposed_rule_text (human-owned once created)
          approved_at, merged_at (set only by human or rule_promoter)
          candidate_rule_id, created_at
        """
        rule = dict(rule)  # shallow copy — avoid mutating the caller's list

        # ── Merge evidence ──────────────────────────────────────────────────
        existing_ev_keys = {self._evidence_key(e) for e in rule.get("evidence", [])}
        for item in self.build_evidence(group):
            if self._evidence_key(item) not in existing_ev_keys:
                rule.setdefault("evidence", []).append(item)
                existing_ev_keys.add(self._evidence_key(item))

        # ── Merge wrong outputs ─────────────────────────────────────────────
        existing_wo_keys = {
            self._output_key({k: v for k, v in w.items() if not k.startswith("_")})
            for w in rule.get("wrong_outputs", [])
        }
        for wo in self.build_wrong_outputs(group):
            key = self._output_key({k: v for k, v in wo.items() if not k.startswith("_")})
            if key not in existing_wo_keys:
                rule.setdefault("wrong_outputs", []).append(wo)
                existing_wo_keys.add(key)

        # ── Merge correct outputs ───────────────────────────────────────────
        existing_co_keys = {
            self._output_key({k: v for k, v in c.items() if not k.startswith("_")})
            for c in rule.get("correct_outputs", [])
        }
        for co in self.build_correct_outputs(group):
            key = self._output_key({k: v for k, v in co.items() if not k.startswith("_")})
            if key not in existing_co_keys:
                rule.setdefault("correct_outputs", []).append(co)
                existing_co_keys.add(key)

        # ── Merge draft texts (reference only — does not touch proposed_rule_text) ──
        existing_drafts = set(rule.get("draft_texts", []))
        for text in self.collect_draft_texts(group):
            if text not in existing_drafts:
                rule.setdefault("draft_texts", []).append(text)
                existing_drafts.add(text)

        # ── Merge restaurants ───────────────────────────────────────────────
        restaurant_set = set(rule.get("restaurants_observed", []))
        for r in self.unique_restaurants(group):
            restaurant_set.add(r)
        rule["restaurants_observed"] = sorted(restaurant_set)

        # ── Recompute times_observed from deduplicated evidence ─────────────
        rule["times_observed"] = len(rule["evidence"])

        # ── Safety-critical is sticky ───────────────────────────────────────
        if self.is_safety_critical(group):
            rule["safety_critical"] = True

        # ── Re-evaluate promotion status ────────────────────────────────────
        prev_status = rule["promotion_status"]
        new_status = self.evaluate_status(
            rule["safety_critical"],
            rule["times_observed"],
            rule["restaurants_observed"],
            prev_status,
        )
        rule["promotion_status"] = new_status
        if new_status == "ready_for_review" and not rule.get("promoted_at"):
            rule["promoted_at"] = self.run_ts

        rule["last_updated_at"] = self.run_ts
        return rule

    # ── Registry management ────────────────────────────────────────────────────

    def load_candidate_rules(self) -> list[dict]:
        """Load existing candidate_rules.json. Returns [] if file does not exist."""
        if not self.output_file.exists():
            return []
        try:
            data = json.loads(self.output_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                sys.exit(f"Error: {self.output_file} must contain a JSON array.")
            return data
        except (json.JSONDecodeError, OSError) as exc:
            sys.exit(f"Error loading {self.output_file}: {exc}")

    def build_rule_index(self, rules: list[dict]) -> dict[str, int]:
        """Map group_key → index in rules list for O(1) lookups."""
        return {
            self.group_key(
                r.get("domain", ""),
                r.get("rule_type", ""),
                r.get("trigger_key", ""),
            ): i
            for i, r in enumerate(rules)
        }

    def save_candidate_rules(self, rules: list[dict]) -> None:
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(
            json.dumps(rules, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Full extraction run. Returns summary stats.

        Steps:
          1. Scan for correction files.
          2. Load and validate each file.
          3. Filter by domain.
          4. Group corrections by (domain, rule_type, trigger_key).
          5. Load existing candidate_rules.json.
          6. Create new rules or update existing ones.
          7. Save updated candidate_rules.json.
        """
        D = "═" * 60
        d = "─" * 60
        print(f"\n{D}")
        print(f"  GoldPan™ Rule Learning Extractor v{EXTRACTOR_VERSION}")
        print(f"  Domain  : {self.domain}")
        print(f"  Packets : {self.packets_dir}")
        print(f"  Output  : {self.output_file}")
        if self.dry_run:
            print("  Mode    : DRY RUN — no files written")
        print(f"{D}\n")

        # Step 1-3: Scan, load, filter
        correction_paths = self.scan_correction_files()
        print(f"Correction files found : {len(correction_paths)}")

        loaded: list[dict] = []
        for path in correction_paths:
            data = self.load_correction_file(path)
            if data:
                loaded.append(data)
        print(f"Correction files valid : {len(loaded)}")

        filtered = self.filter_by_domain(loaded)
        total_corrections = sum(len(f["corrections"]) for f in filtered)
        print(f"After domain filter    : {len(filtered)} file(s), {total_corrections} correction(s)\n")

        if not filtered:
            print("No corrections to process.")
            return {"new": 0, "updated": 0, "promoted": 0, "total_rules": 0}

        # Step 4: Group
        groups = self.group_corrections(filtered)
        print(f"Patterns detected      : {len(groups)}\n")
        print(d)

        # Step 5: Load existing rules
        existing_rules = self.load_candidate_rules()
        rule_index     = self.build_rule_index(existing_rules)

        # Step 6: Process groups
        new_count      = 0
        updated_count  = 0
        promoted_count = 0

        for gk, group in groups.items():
            domain_str, rule_type, trigger_key = gk.split("|", 2)
            restaurants = self.unique_restaurants(group)
            safety = self.is_safety_critical(group)
            safety_tag = "  🔴 SAFETY-CRITICAL" if safety else ""

            if gk in rule_index:
                idx          = rule_index[gk]
                prev_status  = existing_rules[idx]["promotion_status"]
                updated      = self.update_rule(existing_rules[idx], group)
                existing_rules[idx] = updated
                new_status   = updated["promotion_status"]
                action_label = f"↺  Updated   [{prev_status} → {new_status}]"
                updated_count += 1
                if new_status == "ready_for_review" and prev_status != "ready_for_review":
                    promoted_count += 1
            else:
                new_rule    = self.create_rule(group, existing_rules)
                existing_rules.append(new_rule)
                rule_index[gk] = len(existing_rules) - 1
                new_status  = new_rule["promotion_status"]
                action_label = f"✚  New rule  [{new_status}]"
                new_count   += 1
                if new_status == "ready_for_review":
                    promoted_count += 1

            print(f"{action_label}{safety_tag}")
            print(f"   {rule_type}  /  {trigger_key}")
            print(f"   Observations: {len(group)}  |  Restaurants: {len(restaurants)}")
            print()

        # Step 7: Save
        print(d)
        if not self.dry_run:
            self.save_candidate_rules(existing_rules)
            print(f"Saved: {self.output_file.name}  ({len(existing_rules)} total rules)")
        else:
            print(f"[DRY RUN] Would save {len(existing_rules)} rules to {self.output_file.name}")

        stats = {
            "new":         new_count,
            "updated":     updated_count,
            "promoted":    promoted_count,
            "total_rules": len(existing_rules),
        }
        print(f"\n{D}")
        print(f"  {new_count} new  ·  {updated_count} updated  ·  {promoted_count} newly promoted to ready_for_review")
        print(f"  Total rules in registry: {len(existing_rules)}")
        print(f"{D}\n")
        return stats


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rule_extractor.py",
        description=f"GoldPan™ Rule Learning Extractor v{EXTRACTOR_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Promotion thresholds:
  Safety-critical rules  : ready_for_review after {SAFETY_CRITICAL_THRESHOLD} confirmed occurrence(s)
  Standard rules         : ready_for_review after {STANDARD_MIN_RESTAURANTS}+ independent restaurants

Promotion status lifecycle:
  draft → ready_for_review → approved → merged
                           ↘ rejected

The extractor never modifies production standards.
Human approval is mandatory before any rule takes effect.

Domains:
  {sorted(VALID_DOMAINS)} or 'all'

Examples:
  python rule_extractor.py --domain intake
  python rule_extractor.py --domain all --dry-run
  python rule_extractor.py --domain intake --packets-dir ./intake_packets --output ./candidate_rules.json
        """,
    )
    parser.add_argument(
        "--domain",
        default="intake",
        metavar="DOMAIN",
        help="Domain to process (intake | biz_dev | customer_support | operations | all). Default: intake",
    )
    parser.add_argument(
        "--packets-dir",
        type=Path,
        default=INTAKE_PACKETS_DIR,
        metavar="PATH",
        help=f"Directory to scan for *_corrections.json files. Default: {INTAKE_PACKETS_DIR}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CANDIDATE_RULES_FILE,
        metavar="PATH",
        help=f"Path to candidate_rules.json. Default: {CANDIDATE_RULES_FILE}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing any files",
    )

    args   = parser.parse_args()
    runner = RuleLearningExtractor(
        domain      = args.domain,
        packets_dir = args.packets_dir,
        output_file = args.output,
        dry_run     = args.dry_run,
    )
    runner.run()


if __name__ == "__main__":
    main()
