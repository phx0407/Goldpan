#!/usr/bin/env python3
"""
GoldPan™ Restaurant Intake Agent v1.4.0
Standalone canvassing agent — implements docs/INTAKE_AGENT_STANDARD.md

Large menu handling: menus over 40,000 chars are split into sections and
processed chunk-by-chunk. Section packets are saved for audit; results are
merged into one final restaurant-level packet.

Model selection: Haiku by default. Automatic escalation to Sonnet on quality
signals. Use --model sonnet to force Sonnet.

Multi-source input model:
  --url          Primary menu URL (required). Typically an ordering platform or
                 direct menu page. Sets source_type = ordering_platform or menu.
  --website-url  Restaurant's official website. Used to populate location,
                 restaurant_address, hours, restaurant_website, menu_statement.
  --allergen-url Dedicated allergen guide URL. Sets source_type = allergen_guide.
  --nutrition-url Nutrition document URL. Sets source_type = nutrition_document.

  When only --url is provided, the agent completes menu intake and adds Review
  Flags for any restaurant-level operational fields it cannot determine (address,
  hours, website). This is not an extraction failure — it signals canvassing gaps
  to be resolved via a follow-up source URL or restaurant confirmation.

Usage:
  Single run (menu only):
    python intake_agent.py --restaurant "Name" --url "https://..."

  Single run (menu + website):
    python intake_agent.py --restaurant "Name" --url "https://menu..." \
        --website-url "https://website..."

  Single run (full multi-source):
    python intake_agent.py --restaurant "Name" --url "https://menu..." \
        --website-url "https://website..." --allergen-url "https://allergen..."

  Force Sonnet:
    python intake_agent.py --model sonnet --restaurant "Name" --url "https://..."

  Batch run:
    python intake_agent.py --batch --queue queue.json
    python intake_agent.py --batch --queue queue.csv

Queue formats:
  JSON: [{"restaurant_name": "...", "menu_url": "..."}, ...]
  CSV:  restaurant_name,menu_url

Requirements:
  pip install anthropic requests python-dotenv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import goldpan_ai_client
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Versioning ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.4.0"
SCHEMA_VERSION = "1.0"

# ── Paths ──────────────────────────────────────────────────────────────────────
GOLDPAN_ROOT      = Path(__file__).parent
DOCS_DIR          = GOLDPAN_ROOT / "docs"
INTAKE_PACKETS_DIR = GOLDPAN_ROOT / "intake_packets"
SECTIONS_DIR      = INTAKE_PACKETS_DIR / "sections"
CANDIDATE_SCHEMA_FILE = GOLDPAN_ROOT / "candidate_schema_report.json"
INTAKE_STANDARD_FILE  = DOCS_DIR / "INTAKE_AGENT_STANDARD.md"

# ── Models ─────────────────────────────────────────────────────────────────────
MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
}
DEFAULT_MODEL_KEY = "haiku"

# ── Chunking ───────────────────────────────────────────────────────────────────
CHUNK_THRESHOLD = 40_000   # chars — menus over this are chunked
MAX_CHUNK_CHARS = 2_500    # chars — target max per chunk (6x expansion → ~15K JSON output per chunk)

# ── HTTP ───────────────────────────────────────────────────────────────────────
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ══════════════════════════════════════════════════════════════════════════════
# Escalation Policy
# ══════════════════════════════════════════════════════════════════════════════

class EscalationPolicy:
    """
    When to escalate from Haiku to Sonnet.
    Menu size is NOT an escalation trigger — large menus are handled by chunking.
    """

    def __init__(
        self,
        max_review_flags: int = 10,
        max_flag_to_dish_ratio: float = 0.5,
        min_pdfs_for_escalation: int = 2,
    ):
        self.max_review_flags = max_review_flags
        self.max_flag_to_dish_ratio = max_flag_to_dish_ratio
        self.min_pdfs_for_escalation = min_pdfs_for_escalation

    def post_run(self, packet: dict) -> list[str]:
        reasons: list[str] = []
        flags  = packet.get("review_flags", [])
        dishes = packet.get("dishes", [])

        if len(flags) > self.max_review_flags:
            reasons.append(
                f"Review flags ({len(flags)}) exceed threshold ({self.max_review_flags})"
            )
        if dishes:
            ratio = len(flags) / len(dishes)
            if ratio > self.max_flag_to_dish_ratio:
                reasons.append(
                    f"Flag-to-dish ratio ({ratio:.1%}) exceeds threshold "
                    f"({self.max_flag_to_dish_ratio:.0%})"
                )
        for flag in flags:
            if "conflict" in flag.get("type", "").lower() or \
               "conflict" in flag.get("reason", "").lower():
                reasons.append(f"Source conflict detected: {flag.get('type', '?')}")
                break

        sources   = packet.get("restaurant", {}).get("source_inventory", [])
        pdf_count = sum(
            1 for s in sources
            if (isinstance(s, dict) and s.get("type", "").lower() == "pdf")
            or (isinstance(s, str) and s.lower().endswith(".pdf"))
        )
        if pdf_count >= self.min_pdfs_for_escalation:
            reasons.append(f"Multiple PDFs require reconciliation ({pdf_count})")

        return reasons


# ══════════════════════════════════════════════════════════════════════════════
# IntakePipeline
# ══════════════════════════════════════════════════════════════════════════════

class IntakePipeline:
    """
    Core extraction pipeline — identical logic for single and batch modes.

    Large menu flow  (> CHUNK_THRESHOLD chars):
      Split by section → process each chunk → merge → post-process

    Standard flow (≤ CHUNK_THRESHOLD chars):
      Single Claude call → escalation checks → post-process
    """

    # ── Class constants ────────────────────────────────────────────────────────
    VERIFIED_SOURCES = frozenset({
        "menu", "website", "allergen_guide", "nutrition_document",
        "ordering_platform", "pdf", "restaurant_confirmation", "restaurant_qa",
    })
    INGREDIENT_SCORED_FIELDS = ["name", "ingredient_source", "role", "preparation", "type"]
    REQUIRED_METADATA_KEYS   = {
        "agent_version", "schema_version", "model", "execution_mode",
        "started_at", "completed_at", "processing_time_ms",
        "input_sources", "escalated", "packet_hash", "schema_fields",
    }

    def __init__(
        self,
        force_model_key: str | None = None,
        policy: EscalationPolicy | None = None,
    ):
        self.force_model_key    = force_model_key
        self.policy             = policy or EscalationPolicy()
        self.system_prompt      = self._load_standard()
        self._intake_session_id = ""  # set per-run in run()

    # ── Standard loading ───────────────────────────────────────────────────────

    def _load_standard(self) -> str:
        if not INTAKE_STANDARD_FILE.exists():
            sys.exit(f"Error: Intake standard not found at {INTAKE_STANDARD_FILE}")
        return INTAKE_STANDARD_FILE.read_text(encoding="utf-8")

    # ── Menu acquisition ───────────────────────────────────────────────────────

    def fetch_menu_url(self, url: str) -> str:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text

    def load_menu_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    # ── Text extraction from HTML ──────────────────────────────────────────────

    def _extract_text(self, content: str) -> str:
        """
        Strip HTML tags from content and return clean plain text.
        Preserves structure by inserting newlines at block elements.
        """
        is_html = bool(re.search(r'<(html|body|div|section|head)\b', content, re.IGNORECASE))
        if not is_html:
            return content

        # Remove script/style blocks entirely
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>',  '', text,    flags=re.DOTALL | re.IGNORECASE)

        # Block elements → newline
        text = re.sub(r'<(h[1-6]|p|div|section|article|header|footer|nav|li|tr|hr)[^>]*>',
                      '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

        # Strip remaining tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities
        text = html_lib.unescape(text)

        # Normalize whitespace
        lines = [ln.strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln]
        return '\n'.join(lines)

    # ── Section splitting ──────────────────────────────────────────────────────

    # Patterns that strongly suggest a menu section heading
    _HEADING_PATTERNS = [
        re.compile(r'^[A-Z][A-Z\s&/\-]{2,}$'),                          # ALL CAPS
        re.compile(r'^[A-Z][A-Z\s&/\-]+\s+\$\d+'),                     # ALL CAPS + $price (e.g. SALADS $20)
        re.compile(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)* \$\d'),             # Title Case + $price
        re.compile(r'^[-=]{3,}'),                                         # HR separator
        re.compile(r'^\*{2}.+\*{2}$'),                                   # **Bold**
        re.compile(r'^#{1,3} '),                                          # Markdown heading
    ]

    def _is_heading(self, line: str) -> bool:
        line = line.strip()
        if not line or len(line) > 80:
            return False
        return any(p.match(line) for p in self._HEADING_PATTERNS)

    def _split_into_sections(self, text: str) -> list[tuple[str, str]]:
        """
        Split plain text into (section_name, section_content) pairs.
        Falls back to character-based splitting if no headings detected.
        """
        lines = text.splitlines()
        cut_points: list[int] = []

        for i, line in enumerate(lines):
            if self._is_heading(line):
                cut_points.append(i)

        if not cut_points:
            # No headings found — split by character budget
            return self._split_by_chars(text)

        # Ensure we start at line 0 if first heading isn't there
        if cut_points[0] != 0:
            cut_points.insert(0, 0)

        raw_sections: list[tuple[str, str]] = []
        for idx, start in enumerate(cut_points):
            end   = cut_points[idx + 1] if idx + 1 < len(cut_points) else len(lines)
            block = lines[start:end]
            name  = block[0].strip() if block else f"Section {idx + 1}"
            body  = '\n'.join(block)
            if body.strip():
                raw_sections.append((name, body))

        return self._normalize_chunks(raw_sections)

    def _split_by_chars(self, text: str) -> list[tuple[str, str]]:
        """Character-budget split at paragraph boundaries."""
        chunks: list[tuple[str, str]] = []
        current_lines: list[str] = []
        current_len = 0
        chunk_num   = 1

        for line in text.splitlines():
            if current_len + len(line) + 1 > MAX_CHUNK_CHARS and current_lines:
                chunks.append((f"Section {chunk_num}", '\n'.join(current_lines)))
                chunk_num  += 1
                current_lines = [line]
                current_len   = len(line)
            else:
                current_lines.append(line)
                current_len += len(line) + 1

        if current_lines:
            chunks.append((f"Section {chunk_num}", '\n'.join(current_lines)))

        return chunks

    def _normalize_chunks(
        self, sections: list[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        """Merge tiny adjacent sections; sub-split oversized ones."""
        result: list[tuple[str, str]] = []
        pending_name = ""
        pending_text = ""

        for name, text in sections:
            if pending_text and len(pending_text) + len(text) + 2 <= MAX_CHUNK_CHARS:
                pending_text += "\n\n" + text
            else:
                if pending_text:
                    result.append((pending_name, pending_text))
                if len(text) > MAX_CHUNK_CHARS:
                    sub = self._split_by_chars(text)
                    for i, (_, chunk) in enumerate(sub):
                        result.append((f"{name} (part {i + 1})", chunk))
                    pending_name = ""
                    pending_text = ""
                    continue
                pending_name = name
                pending_text = text

        if pending_text:
            result.append((pending_name or "Final Section", pending_text))

        return result

    # ── JSON recovery ──────────────────────────────────────────────────────────

    def _extract_json_substring(self, text: str) -> str | None:
        """
        Extract a JSON object or array from text that may contain surrounding prose.
        Finds the first { or [ (whichever appears first) and the last matching } or ].
        Returns the extracted substring, or None if no valid bounds found.
        """
        first_brace   = text.find('{')
        first_bracket = text.find('[')

        if first_brace == -1 and first_bracket == -1:
            return None

        if first_brace == -1:
            start, end_char = first_bracket, ']'
        elif first_bracket == -1:
            start, end_char = first_brace, '}'
        else:
            if first_brace <= first_bracket:
                start, end_char = first_brace, '}'
            else:
                start, end_char = first_bracket, ']'

        end = text.rfind(end_char)
        if end == -1 or end <= start:
            return None
        return text[start:end + 1]

    # ── Claude calls ───────────────────────────────────────────────────────────

    def _build_full_prompt(
        self,
        restaurant_name: str,
        url: str,
        menu_content: str,
        additional_sources: dict[str, tuple[str, str]] | None = None,
    ) -> str:
        """
        Build the full extraction prompt.

        additional_sources: dict mapping source_type → (source_url, extracted_text)
          e.g. {"website": ("https://...", "page text"), "allergen_guide": ("https://...", "...")}
        """
        additional_blocks = ""
        if additional_sources:
            for source_type, (src_url, src_text) in additional_sources.items():
                additional_blocks += f"""
Additional Source — {source_type} ({src_url}):
---
{src_text[:6000]}
---
"""
        return f"""Canvass the following restaurant and produce a complete GoldPan™ intake packet.

Restaurant Name: {restaurant_name}
Menu URL: {url}
Canvass Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

Menu Content:
---
{menu_content}
---
{additional_blocks}
{self._output_schema_instructions()}"""

    def _build_section_prompt(
        self, restaurant_name: str, url: str, section_name: str, section_text: str
    ) -> str:
        return f"""You are processing ONE SECTION of a larger menu for GoldPan™.
Capture only the dishes present in this section. Do not invent dishes not shown here.

Restaurant Name: {restaurant_name}
Menu URL: {url}
Section: {section_name}
Canvass Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

Section Content:
---
{section_text}
---

{self._output_schema_instructions(section_mode=True)}"""

    def _output_schema_instructions(self, section_mode: bool = False) -> str:
        restaurant_block = '' if section_mode else '''{
  "restaurant": {
    "restaurant_name": "",
    "location": "",
    "restaurant_address": "",
    "restaurant_website": "",
    "hours": "",
    "menu_link": "",
    "menu_statement": "",
    "source_inventory": [],
    "canvass_date": "",
    "reviewer_status": "pending_review",
    "restaurant_claims": []
  },'''

        return f"""Produce a complete intake packet as valid JSON with this structure:

{{{restaurant_block}
  "dishes": [
    {{
      "dish_name": "",
      "menu_section": "",
      "category": "",
      "description": "",
      "price": "",
      "stated_tags": [],
      "tag_source": "",
      "modifiers": [],
      "ingredients": [
        {{
          "name": "",
          "ingredient_source": "",
          "role": "",
          "preparation": "",
          "type": "",
          "cut_type": "",
          "allergen_flags": []
        }}
      ],
      "verbatim_components": [
        {{
          "verbatim_text": "",
          "ingredient_source": "",
          "resolution_status": "unresolved"
        }}
      ],
      "allergen_disclosures": []
    }}
  ],
  "review_flags": [{{"type":"","dish":"","phrase":"","reason":"","suggested_action":""}}],
  "advisory_notes": [{{"note":"","dish":""}}],
  "candidate_schema_report": [
    {{
      "proposed_field_name":"","description":"","example_values":[],
      "supporting_menu_text":"","restaurants_observed":1,
      "estimated_frequency_pct":"","recommended_schema_layer":"",
      "classification":"","customer_value":"","search_value":"",
      "ai_reasoning_value":"","governance_complexity":"","confidence":""
    }}
  ]
}}

Rules:
- ingredient_source must be one of: menu, website, allergen_guide, nutrition_document, ordering_platform, pdf, restaurant_confirmation, restaurant_qa
- Generic phrases (house sauce, seasonal vegetables, chef's blend, etc.) → verbatim_components, NOT ingredients
- reviewer_status must be "pending_review"
- Do NOT infer ingredients. Do NOT perform Governance.
- Omit empty arrays and blank fields to reduce output size.
- Return ONLY valid JSON.
- Do not include markdown.
- Do not include explanations.
- Do not wrap output in code fences.
- Do not include comments.

Restaurant-level field rules:
- location: neighborhood, city, or district only (e.g. "Bessemer, AL"). From official source. Leave blank if not found.
- restaurant_address: full street address from official source. Leave blank if not found.
- restaurant_website: official restaurant website URL. Do not use ordering platform URL unless that is the only official web presence.
- hours: verbatim from official source. Format: "Day-Day: H:MM AM/PM - H:MM AM/PM". Leave blank if not found.
- menu_link: primary public menu URL. Use the URL of the menu page being canvassed if no separate menu link exists.
- menu_statement: verbatim restaurant description or mission statement from an official source. Leave blank if not found.
- restaurant_claims: explicit claims made by the restaurant about itself (plant-based, vegan, organic, halal, etc.). Only populate from verified source text.
- If restaurant_address, hours, or restaurant_website cannot be determined from the provided source(s), add a Review Flag for each missing field with type "Missing Operational Field" and suggested_action "Provide [field] source URL or restaurant confirmation".

Dish-level field rules:
- category: the menu section this dish belongs to (e.g. "Salads", "Soups", "Entrées", "Raw Food Meals"). Use the section header, normalized. Do not infer category from dish description.
- stated_tags: only explicit dietary labels the restaurant places on individual dishes (e.g. "Vegan", "Gluten-Free", "Halal"). Leave [] if the restaurant does not explicitly label individual dishes. Do NOT infer tags from ingredients.
- tag_source: the approved source enum value (menu, website, ordering_platform, etc.) for the stated_tags. Leave blank if stated_tags is []."""

    def _call_claude(
        self,
        prompt: str,
        model_key: str,
        label: str = "",
        purpose: str = "intake",
    ) -> dict | None:
        """
        Single Claude call. Returns parsed dict or None on JSON failure.

        Recovery sequence (before escalation or failure):
          1. Parse raw output as-is.
          2. Strip markdown fences, retry.
          3. Extract JSON by removing prose before first { or [ and after last } or ].
          4. If recovered text still fails to parse, save debug files and return None.

        For Sonnet failures, saves both raw output and recovered candidate for inspection.
        BudgetExceededError propagates — callers should not silently swallow it.
        """
        message = goldpan_ai_client.call(
            model=MODELS[model_key],
            purpose=purpose,
            messages=[{"role": "user", "content": prompt}],
            system=self.system_prompt,
            max_tokens=16384,
            session_id=self._intake_session_id,
        )

        raw = message.content[0].text.strip()
        INTAKE_PACKETS_DIR.mkdir(exist_ok=True)
        ts = int(time.time())

        # Step 1: parse as-is
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Step 2: strip markdown fences and retry
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Step 3: remove prose before first { or [ and after last } or ]
        recovered_text = self._extract_json_substring(cleaned)
        if recovered_text is not None:
            try:
                result = json.loads(recovered_text)
                print(f"    ↻ JSON recovered via extraction ({model_key})")
                return result
            except json.JSONDecodeError:
                pass

        # Step 4: all recovery failed — save debug files
        debug_path = INTAKE_PACKETS_DIR / f"_debug_{ts}_{label or 'unknown'}.txt"
        debug_path.write_text(raw)
        print(f"    ⚠ JSON parse failed ({model_key}). Debug: {debug_path.name}")

        # For Sonnet failures, also save the extracted-but-unparseable candidate
        if recovered_text is not None:
            repair_path = INTAKE_PACKETS_DIR / f"_repaired_{ts}_{label or 'unknown'}.txt"
            repair_path.write_text(recovered_text)
            print(f"    ⚠ Extracted candidate saved: {repair_path.name}")

        return None

    # ── Chunked pipeline ───────────────────────────────────────────────────────

    def _run_chunked(
        self,
        restaurant_name: str,
        url: str,
        menu_content: str,
        model_key: str,
        additional_sources: dict[str, tuple[str, str]] | None = None,
    ) -> tuple[dict, list[str]]:
        """
        Process a large menu in sections.
        Returns (merged_packet, escalation_reasons).
        """
        SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

        text     = self._extract_text(menu_content)
        sections = self._split_into_sections(text)
        slug     = re.sub(r"[^a-z0-9]+", "_", restaurant_name.lower()).strip("_")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        print(f"  Chunking: {len(text):,} chars → {len(sections)} sections")

        section_packets: list[dict] = []
        escalation_reasons: list[str] = []
        current_model = model_key

        for i, (section_name, section_text) in enumerate(sections, 1):
            short_name = section_name[:40].strip()
            print(f"  [{i}/{len(sections)}] {short_name!r} ({len(section_text):,} chars) — {current_model}")

            prompt = self._build_section_prompt(restaurant_name, url, section_name, section_text)
            packet = self._call_claude(prompt, current_model, label=f"s{i}")

            # JSON failure escalation
            if packet is None and current_model == "haiku":
                reason = f"Section {i} JSON failed on Haiku — escalating to Sonnet"
                escalation_reasons.append(reason)
                current_model = "sonnet"
                print(f"    ↑ Escalating to Sonnet")
                packet = self._call_claude(prompt, current_model, label=f"s{i}_sonnet", purpose="escalation")

            if packet is None:
                print(f"    ✗ Section {i} failed — skipping")
                continue

            # Save section packet for audit
            safe_section = re.sub(r"[^a-z0-9]+", "_", section_name.lower())[:30].strip("_")
            section_path = SECTIONS_DIR / f"{slug}_{date_str}_s{i:02d}_{safe_section}.json"
            section_path.write_text(json.dumps(packet, indent=2))

            section_packets.append(packet)

        merged = self._merge_section_packets(
            restaurant_name, url, section_packets, additional_sources=additional_sources
        )
        return merged, escalation_reasons

    def _merge_section_packets(
        self,
        restaurant_name: str,
        url: str,
        packets: list[dict],
        additional_sources: dict[str, tuple[str, str]] | None = None,
    ) -> dict:
        """Merge section-level packets into one restaurant packet."""
        # Build source_inventory from primary URL + any additional sources
        source_inventory = [{"source_type": "ordering_platform", "url": url}]
        source_type_map = {
            "website":          "website",
            "allergen_guide":   "allergen_guide",
            "nutrition_document": "nutrition_document",
        }
        if additional_sources:
            for src_type, (src_url, _) in additional_sources.items():
                mapped = source_type_map.get(src_type, src_type)
                source_inventory.append({"source_type": mapped, "url": src_url})

        merged: dict = {
            "restaurant": {
                "restaurant_name": restaurant_name,
                "location":           "",
                "restaurant_address": "",
                "restaurant_website": "",
                "hours":              "",
                "menu_link":          url,
                "menu_statement":     "",
                "source_inventory": source_inventory,
                "canvass_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "reviewer_status": "pending_review",
                "restaurant_claims": [],
            },
            "dishes": [],
            "review_flags": [],
            "advisory_notes": [],
            "candidate_schema_report": [],
        }

        seen_candidates: dict[str, bool] = {}

        for packet in packets:
            merged["dishes"].extend(packet.get("dishes", []))
            merged["review_flags"].extend(packet.get("review_flags", []))
            merged["advisory_notes"].extend(packet.get("advisory_notes", []))

            for candidate in packet.get("candidate_schema_report", []):
                field_name = candidate.get("proposed_field_name", "")
                if field_name and field_name not in seen_candidates:
                    seen_candidates[field_name] = True
                    merged["candidate_schema_report"].append(candidate)

        return merged

    # ── Standard (single-call) pipeline ───────────────────────────────────────

    def _run_standard(
        self,
        restaurant_name: str,
        url: str,
        menu_content: str,
        model_key: str,
        additional_sources: dict[str, tuple[str, str]] | None = None,
    ) -> tuple[dict | None, list[str], str]:
        """
        Single-call pipeline with escalation.
        Returns (packet, escalation_reasons, final_model_key).
        """
        escalation_reasons: list[str] = []
        final_model_key = model_key

        print(f"  Calling Claude ({final_model_key})…")
        prompt = self._build_full_prompt(
            restaurant_name, url, menu_content,
            additional_sources=additional_sources,
        )
        packet = self._call_claude(prompt, final_model_key, label="full")

        # JSON failure escalation (Haiku → Sonnet)
        if packet is None and final_model_key == "haiku":
            reason = "JSON validation failed on Haiku — escalating to Sonnet"
            escalation_reasons.append(reason)
            final_model_key = "sonnet"
            print(f"  ↑ Escalating to Sonnet: {reason}")
            packet = self._call_claude(prompt, final_model_key, label="full_sonnet", purpose="escalation")

        if packet is None:
            return None, escalation_reasons, final_model_key

        # Post-run quality escalation
        if final_model_key == "haiku":
            post_reasons = self.policy.post_run(packet)
            if post_reasons:
                escalation_reasons.extend(post_reasons)
                final_model_key = "sonnet"
                for r in post_reasons:
                    print(f"  ↑ Escalating to Sonnet: {r}")
                packet = self._call_claude(prompt, final_model_key, label="full_escalated", purpose="escalation")
                if packet is None:
                    return None, escalation_reasons, final_model_key

        return packet, escalation_reasons, final_model_key

    # ── Scoring & fingerprinting ───────────────────────────────────────────────

    def _compute_evidence_score(self, packet: dict) -> dict:
        dishes = packet.get("dishes", [])
        EMPTY  = {"", "none", "unknown", None}

        if not dishes:
            return {"overall": 0, "source_quality": 0,
                    "ingredient_completeness": 0, "ambiguity": 0, "review_flags": 0}

        total_ings, verified_ings = 0, 0
        for dish in dishes:
            for ing in dish.get("ingredients", []):
                total_ings += 1
                if ing.get("ingredient_source", "").strip() in self.VERIFIED_SOURCES:
                    verified_ings += 1
        source_quality = round(verified_ings / total_ings * 100) if total_ings else 100

        total_fields, populated_fields = 0, 0
        for dish in dishes:
            for ing in dish.get("ingredients", []):
                for field in self.INGREDIENT_SCORED_FIELDS:
                    total_fields += 1
                    val = ing.get(field)
                    if isinstance(val, list):
                        populated_fields += 1 if val else 0
                    elif val not in EMPTY:
                        populated_fields += 1
        ingredient_completeness = round(populated_fields / total_fields * 100) if total_fields else 0

        ambiguity         = sum(len(dish.get("verbatim_components", [])) for dish in dishes)
        review_flags_count = len(packet.get("review_flags", []))

        ambiguity_penalty = min(ambiguity * 4, 20)
        flags_penalty     = min(review_flags_count * 4, 20)
        overall = round(
            source_quality * 0.40
            + ingredient_completeness * 0.40
            + (100 - ambiguity_penalty) * 0.10
            + (100 - flags_penalty) * 0.10
        )

        return {
            "overall":                  max(0, min(100, overall)),
            "source_quality":           source_quality,
            "ingredient_completeness":  ingredient_completeness,
            "ambiguity":                ambiguity,
            "review_flags":             review_flags_count,
        }

    def _snapshot_schema_fields(self, packet: dict) -> list[str]:
        fields: set[str] = set()
        for dish in packet.get("dishes", []):
            for k, v in dish.items():
                if v not in ("", None) and v != [] and v != {}:
                    fields.add(k)
        return sorted(fields)

    def _compute_packet_hash(self, packet: dict) -> str:
        canonical = json.dumps(packet, sort_keys=True, ensure_ascii=False, default=str)
        return "SHA256:" + hashlib.sha256(canonical.encode()).hexdigest()

    # ── Candidate schema persistence ───────────────────────────────────────────

    def _update_candidate_schema(self, new_candidates: list) -> int:
        if not new_candidates:
            return 0
        existing = json.loads(CANDIDATE_SCHEMA_FILE.read_text()) \
            if CANDIDATE_SCHEMA_FILE.exists() else []
        index    = {e["proposed_field_name"]: i for i, e in enumerate(existing)}
        new_count = 0
        for candidate in new_candidates:
            field_name = candidate.get("proposed_field_name", "").strip()
            if not field_name:
                continue
            if field_name in index:
                idx = index[field_name]
                existing[idx]["restaurants_observed"] = existing[idx].get("restaurants_observed", 1) + 1
                example = candidate.get("supporting_menu_text", "")
                if example:
                    existing[idx].setdefault("supporting_examples", []).append(example)
            else:
                existing.append(candidate)
                index[field_name] = len(existing) - 1
                new_count += 1
        CANDIDATE_SCHEMA_FILE.write_text(json.dumps(existing, indent=2))
        return new_count

    # ── Validation report ──────────────────────────────────────────────────────

    def _generate_validation_report(self, packet: dict, output_path: Path) -> tuple[str, str]:
        restaurant_name = packet.get("restaurant", {}).get("restaurant_name", "Unknown")
        canvass_date    = packet.get("restaurant", {}).get("canvass_date", "—")
        meta    = packet.get("agent_metadata", {})
        score   = packet.get("evidence_score", {})
        dishes  = packet.get("dishes", [])
        flags   = packet.get("review_flags", [])
        notes   = packet.get("advisory_notes", [])
        candidates = packet.get("candidate_schema_report", [])

        checks_pass: list[str] = []
        checks_warn: list[str] = []
        checks_fail: list[str] = []

        # reviewer_status
        if packet.get("restaurant", {}).get("reviewer_status") == "pending_review":
            checks_pass.append("reviewer_status = pending_review")
        else:
            checks_fail.append("reviewer_status is not 'pending_review'")

        # packet_hash
        if meta.get("packet_hash", "").startswith("SHA256:"):
            checks_pass.append("packet_hash present and well-formed")
        else:
            checks_fail.append("packet_hash missing or malformed")

        # schema_fields
        if meta.get("schema_fields"):
            checks_pass.append(f"schema_fields snapshot ({len(meta['schema_fields'])} fields)")
        else:
            checks_warn.append("schema_fields snapshot is empty")

        # metadata completeness
        missing = self.REQUIRED_METADATA_KEYS - set(meta.keys())
        if not missing:
            checks_pass.append("agent_metadata complete")
        else:
            checks_fail.append(f"agent_metadata missing: {', '.join(sorted(missing))}")

        # evidence_score
        if score:
            checks_pass.append(f"evidence_score present (overall: {score.get('overall','—')}/100)")
        else:
            checks_fail.append("evidence_score missing")

        # ingredient_source values
        bad_sources: list[str] = []
        dishes_no_content = 0
        for dish in dishes:
            if not dish.get("ingredients") and not dish.get("verbatim_components"):
                dishes_no_content += 1
            for ing in dish.get("ingredients", []):
                src = ing.get("ingredient_source", "").strip()
                if src and src not in self.VERIFIED_SOURCES:
                    bad_sources.append(f"{dish.get('dish_name','?')}: {src!r}")
        if bad_sources:
            for b in bad_sources[:5]:
                checks_fail.append(f"Unrecognized ingredient_source — {b}")
            if len(bad_sources) > 5:
                checks_fail.append(f"… and {len(bad_sources) - 5} more")
        else:
            checks_pass.append("All ingredient_source values are in approved enum")

        if dishes_no_content:
            checks_warn.append(f"{dishes_no_content} dish(es) have no ingredients or verbatim components")

        no_section = sum(1 for d in dishes if not d.get("menu_section", "").strip())
        if no_section:
            checks_warn.append(f"{no_section} dish(es) missing menu_section")

        no_price = sum(1 for d in dishes if not d.get("price", "").strip())
        if no_price:
            checks_warn.append(f"{no_price} dish(es) missing price")

        overall = score.get("overall", 0)
        if overall < 50:
            checks_fail.append(f"Evidence score ({overall}) below minimum threshold (50)")
        elif overall < 70:
            checks_warn.append(f"Evidence score ({overall}) below recommended threshold (70)")

        # Chunked run notes
        chunked = meta.get("chunked", False)
        if chunked:
            n = meta.get("sections_processed", "?")
            checks_pass.append(f"Chunked run: {n} section(s) merged successfully")

        verdict = "FAIL" if checks_fail else ("PASS WITH WARNINGS" if checks_warn else "PASS")

        D = "═" * 56
        d = "─" * 56
        lines = [
            D,
            "  GoldPan™ Intake Validation Report",
            f"  Restaurant : {restaurant_name}",
            f"  Date       : {canvass_date}",
            f"  Model      : {meta.get('model','—')}",
            f"  Chunked    : {'yes (' + str(meta.get('sections_processed','?')) + ' sections)' if chunked else 'no'}",
            f"  Escalated  : {'yes' if meta.get('escalated') else 'no'}",
            D, "",
            "EVIDENCE QUALITY",
            f"  Overall             {score.get('overall','—'):>4}/100",
            f"  Source quality      {score.get('source_quality','—'):>4}",
            f"  Completeness        {score.get('ingredient_completeness','—'):>4}",
            f"  Ambiguity           {score.get('ambiguity','—'):>4}  (verbatim components)",
            f"  Review flags        {score.get('review_flags','—'):>4}",
            "", "VALIDATION CHECKS",
        ]
        for c in checks_pass: lines.append(f"  ✓  {c}")
        for c in checks_warn: lines.append(f"  ⚠  {c}")
        for c in checks_fail: lines.append(f"  ✗  {c}")

        lines += [
            "", "DISHES CAPTURED",
            f"  Total               {len(dishes):>4}",
            f"  With ingredients    {sum(1 for d in dishes if d.get('ingredients')):>4}",
            f"  With verbatim comp. {sum(1 for d in dishes if d.get('verbatim_components')):>4}",
            f"  With allergen disc. {sum(1 for d in dishes if d.get('allergen_disclosures')):>4}",
        ]
        if flags:
            lines += ["", f"REVIEW FLAGS ({len(flags)})"]
            for i, f_ in enumerate(flags[:10], 1):
                dish_ref = f" ({f_.get('dish','')})" if f_.get("dish") else ""
                phrase   = f" — \"{f_.get('phrase','')}\"" if f_.get("phrase") else ""
                lines.append(f"  {i}. {f_.get('type','Unknown')}{phrase}{dish_ref}")
            if len(flags) > 10:
                lines.append(f"  … and {len(flags)-10} more (see packet JSON)")
        if notes:
            lines += ["", f"ADVISORY NOTES ({len(notes)})"]
            for i, n in enumerate(notes[:5], 1):
                lines.append(f"  {i}. {n.get('note','')}")
        if candidates:
            lines += ["", f"SCHEMA CANDIDATES ({len(candidates)} this run)"]
            for c in candidates[:5]:
                lines.append(f"  · {c.get('proposed_field_name','?')} "
                              f"[{c.get('recommended_schema_layer','?')}] "
                              f"— confidence: {c.get('confidence','?')}")
            if len(candidates) > 5:
                lines.append(f"  … and {len(candidates)-5} more")
        else:
            lines += ["", "SCHEMA CANDIDATES", "  None discovered this run"]

        lines += ["", d, f"  VERDICT: {verdict}", f"  Packet : {output_path.name}", d]
        return "\n".join(lines), verdict

    # ── Output ─────────────────────────────────────────────────────────────────

    def _save_packet(self, restaurant_name: str, packet: dict) -> Path:
        INTAKE_PACKETS_DIR.mkdir(exist_ok=True)
        slug     = re.sub(r"[^a-z0-9]+", "_", restaurant_name.lower()).strip("_")
        filename = f"{slug}_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
        path     = INTAKE_PACKETS_DIR / filename
        path.write_text(json.dumps(packet, indent=2))
        return path

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(
        self,
        restaurant_name: str,
        url: str,
        menu_content: str,
        execution_mode: str = "single",
        additional_sources: dict[str, tuple[str, str]] | None = None,
    ) -> tuple[dict, Path, str, str]:
        """
        Full pipeline for one restaurant. Branches on menu size.

        additional_sources: dict mapping source_type → (source_url, extracted_text)
          Used to populate restaurant-level operational fields (address, hours, etc.)
          and to support allergen_guide / nutrition_document extraction.

        Returns (packet, output_path, report_text, verdict).
        """
        started_at = datetime.now(timezone.utc)
        started_ms = time.monotonic_ns() // 1_000_000

        # ── Session ID for AI usage logging ────────────────────────────────────
        slug = re.sub(r"[^a-z0-9]+", "_", restaurant_name.lower()).strip("_")
        self._intake_session_id = f"intake-{slug}-{started_at.strftime('%Y%m%dT%H%M%S')}"

        # ── Choose starting model ──────────────────────────────────────────────
        model_key = self.force_model_key if self.force_model_key else DEFAULT_MODEL_KEY

        # ── Build combined prompt (with additional sources if any) ─────────────
        # For the standard (non-chunked) path, additional_sources are embedded
        # in the prompt. For chunked paths, they're passed to the merge step.
        text_for_size_check = self._extract_text(menu_content)

        # ── Route to chunked or standard ──────────────────────────────────────
        chunked = len(menu_content) > CHUNK_THRESHOLD
        escalation_reasons: list[str] = []
        final_model_key = model_key
        sections_processed = 0

        if chunked:
            print(f"  Large menu detected ({len(menu_content):,} chars) — chunked mode")
            packet, escalation_reasons = self._run_chunked(
                restaurant_name, url, menu_content, model_key,
                additional_sources=additional_sources,
            )
            sections_processed = len(self._split_into_sections(text_for_size_check))
        else:
            packet, escalation_reasons, final_model_key = self._run_standard(
                restaurant_name, url, menu_content, model_key,
                additional_sources=additional_sources,
            )

        if packet is None:
            sys.exit("Error: All Claude calls failed. Check _debug_*.txt in intake_packets/")

        # ── Enforce reviewer_status ────────────────────────────────────────────
        packet.setdefault("restaurant", {})["reviewer_status"] = "pending_review"
        packet["restaurant"]["canvass_date"] = started_at.strftime("%Y-%m-%d")

        # ── Candidate schema ───────────────────────────────────────────────────
        candidates = packet.get("candidate_schema_report", [])
        new_count  = self._update_candidate_schema(candidates)

        # ── Evidence score ─────────────────────────────────────────────────────
        packet["evidence_score"] = self._compute_evidence_score(packet)

        # ── Agent metadata ─────────────────────────────────────────────────────
        completed_at = datetime.now(timezone.utc)
        completed_ms = time.monotonic_ns() // 1_000_000

        # For chunked runs, report the model used most (haiku unless escalated)
        display_model = MODELS.get(final_model_key, MODELS[model_key])
        if chunked and escalation_reasons:
            display_model = MODELS["sonnet"]
        elif chunked:
            display_model = MODELS[model_key]

        packet["agent_metadata"] = {
            "agent_version":       AGENT_VERSION,
            "schema_version":      SCHEMA_VERSION,
            "model":               display_model,
            "execution_mode":      execution_mode,
            "chunked":             chunked,
            "sections_processed":  sections_processed if chunked else 0,
            "started_at":          started_at.isoformat(),
            "completed_at":        completed_at.isoformat(),
            "processing_time_ms":  completed_ms - started_ms,
            "input_sources":       [url],
            "escalated":           len(escalation_reasons) > 0,
            "escalation_reasons":  escalation_reasons,
        }

        # ── Schema fields snapshot ─────────────────────────────────────────────
        packet["agent_metadata"]["schema_fields"] = self._snapshot_schema_fields(packet)

        # ── Packet fingerprint (must be last) ──────────────────────────────────
        packet["agent_metadata"]["packet_hash"] = self._compute_packet_hash(packet)

        # ── Save packet ────────────────────────────────────────────────────────
        output_path = self._save_packet(restaurant_name, packet)

        # ── Validation report ──────────────────────────────────────────────────
        report_text, verdict = self._generate_validation_report(packet, output_path)
        report_path = output_path.with_name(output_path.stem + "_validation.txt")
        report_path.write_text(report_text, encoding="utf-8")

        # ── Console summary ────────────────────────────────────────────────────
        elapsed = (completed_ms - started_ms) / 1000
        score   = packet["evidence_score"]
        mode_label = f"chunked ({sections_processed} sections)" if chunked else "standard"
        print(f"  ✓ {len(packet.get('dishes',[]))} dishes "
              f"· {len(packet.get('review_flags',[]))} flags "
              f"· score {score.get('overall','—')}/100 [{mode_label}]")
        if escalation_reasons:
            print(f"  ↑ Escalated ({len(escalation_reasons)} reason(s))")
        if candidates:
            print(f"  ✓ Schema candidates: {len(candidates)} processed, {new_count} new")
        print(f"  ✓ {elapsed:.1f}s · Packet: {output_path.name} · [{verdict}]")
        if chunked:
            print(f"  ✓ Section packets saved in intake_packets/sections/")

        return packet, output_path, report_text, verdict


# ══════════════════════════════════════════════════════════════════════════════
# Execution modes
# ══════════════════════════════════════════════════════════════════════════════

def run_single(args, pipeline: IntakePipeline):
    print(f"\nGoldPan™ Intake Agent v{AGENT_VERSION} — Single Run")
    print(f"Restaurant : {args.restaurant}")
    print()

    if args.file:
        print(f"  Loading menu from file: {args.file}")
        menu_content = pipeline.load_menu_file(args.file)
        url = args.url or f"file://{Path(args.file).resolve()}"
    else:
        print(f"  Fetching menu: {args.url}")
        try:
            menu_content = pipeline.fetch_menu_url(args.url)
        except requests.RequestException as e:
            sys.exit(
                f"Error fetching URL: {e}\n"
                "Tip: If the menu is JavaScript-rendered, save page text to a file and use --file."
            )
        url = args.url
        print(f"  Fetched {len(menu_content):,} chars.")

    # ── Collect additional sources ────────────────────────────────────────────
    # Maps source_type → (source_url, extracted_text)
    _additional_source_args = [
        ("website",             getattr(args, "website_url",    None)),
        ("allergen_guide",      getattr(args, "allergen_url",   None)),
        ("nutrition_document",  getattr(args, "nutrition_url",  None)),
    ]
    additional_sources: dict[str, tuple[str, str]] = {}
    for src_type, src_url in _additional_source_args:
        if not src_url:
            continue
        print(f"  Fetching {src_type}: {src_url}")
        try:
            raw = pipeline.fetch_menu_url(src_url)
            text = pipeline._extract_text(raw)
            additional_sources[src_type] = (src_url, text)
            print(f"  Fetched {len(text):,} chars ({src_type}).")
        except requests.RequestException as e:
            print(f"  ⚠ Could not fetch {src_type} ({src_url}): {e} — skipping")

    packet, output_path, report_text, verdict = pipeline.run(
        args.restaurant, url, menu_content,
        execution_mode="single",
        additional_sources=additional_sources or None,
    )

    print()
    print(report_text)
    print()
    print("Ready for human review before entering the database.")


def run_batch(args, pipeline: IntakePipeline):
    queue_file = Path(args.queue)
    if not queue_file.exists():
        sys.exit(f"Error: queue file not found: {queue_file}")

    if queue_file.suffix == ".json":
        queue = json.loads(queue_file.read_text())
    elif queue_file.suffix == ".csv":
        with open(queue_file, newline="", encoding="utf-8") as f:
            queue = list(csv.DictReader(f))
    else:
        sys.exit("Error: queue file must be .json or .csv")

    print(f"\nGoldPan™ Intake Agent v{AGENT_VERSION} — Batch Run")
    print(f"Queue  : {queue_file} ({len(queue)} restaurants)")
    print()

    results = []
    for i, item in enumerate(queue, 1):
        restaurant_name = (item.get("restaurant_name") or item.get("name", "")).strip()
        url             = (item.get("menu_url")  or item.get("url",  "")).strip()
        file_path       = item.get("menu_file", "").strip()

        if not restaurant_name:
            print(f"[{i}/{len(queue)}] Skipping — missing restaurant_name"); continue
        if not url and not file_path:
            print(f"[{i}/{len(queue)}] Skipping {restaurant_name!r} — missing menu_url"); continue

        print(f"[{i}/{len(queue)}] {restaurant_name}")
        try:
            if file_path:
                menu_content  = pipeline.load_menu_file(file_path)
                effective_url = url or f"file://{Path(file_path).resolve()}"
            else:
                print(f"  Fetching: {url}")
                menu_content  = pipeline.fetch_menu_url(url)
                print(f"  Fetched {len(menu_content):,} chars.")
                effective_url = url

            packet, output_path, _report, verdict = pipeline.run(
                restaurant_name, effective_url, menu_content, execution_mode="batch"
            )
            meta = packet.get("agent_metadata", {})
            results.append({
                "restaurant": restaurant_name,
                "dishes":  len(packet.get("dishes", [])),
                "flags":   len(packet.get("review_flags", [])),
                "score":   packet.get("evidence_score", {}).get("overall", "—"),
                "chunked": meta.get("chunked", False),
                "verdict": verdict,
                "output":  output_path.name,
                "status":  "ok",
            })
        except SystemExit: raise
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({"restaurant": restaurant_name, "status": "error", "error": str(e)})
        print()

    ok     = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]
    print(f"{'═'*56}")
    print(f"Batch: {len(ok)} succeeded · {len(errors)} failed")
    print(f"{'─'*56}")
    for r in ok:
        chunked_tag = " [chunked]" if r.get("chunked") else ""
        print(f"  ✓ {r['restaurant']}: {r['dishes']} dishes · "
              f"score {r['score']}/100 · {r['verdict']}{chunked_tag} → {r['output']}")
    for r in errors:
        print(f"  ✗ {r['restaurant']}: {r['error']}")
    print(f"{'═'*56}")
    print("All packets are pending_review.")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="intake_agent.py",
        description=f"GoldPan™ Restaurant Intake Agent v{AGENT_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Large menu handling (> 40,000 chars):
  Automatically splits by section, processes each chunk separately,
  saves section packets to intake_packets/sections/ for audit,
  then merges into one final restaurant packet.

Escalation triggers (Haiku → Sonnet):
  - JSON validation fails
  - Review flags exceed threshold (default: 10)
  - Flag-to-dish ratio exceeds 50%
  - Source conflict detected
  - Multiple PDFs in source inventory

Examples:
  python intake_agent.py --restaurant "Name" --url "https://..."
  python intake_agent.py --model sonnet --restaurant "Name" --url "https://..."
  python intake_agent.py --batch --queue queue.json
        """,
    )
    parser.add_argument("--model", choices=["haiku", "sonnet"], default=None,
                        help="Force a model. Default: auto (Haiku + escalation)")
    parser.add_argument("--batch",      action="store_true")
    parser.add_argument("--restaurant", help="Restaurant name (single mode)")
    parser.add_argument("--url",        help="Primary menu URL (ordering platform or menu page)")
    parser.add_argument("--website-url",   dest="website_url",
                        help="Restaurant's official website URL (for address, hours, etc.)")
    parser.add_argument("--allergen-url",  dest="allergen_url",
                        help="Dedicated allergen guide URL")
    parser.add_argument("--nutrition-url", dest="nutrition_url",
                        help="Nutrition document URL")
    parser.add_argument("--file",       help="Local menu text file (JS-rendered fallback)")
    parser.add_argument("--queue",      help="Queue file (.json or .csv) for batch mode")

    args = parser.parse_args()
    pipeline = IntakePipeline(force_model_key=args.model)

    if args.batch:
        if not args.queue:
            parser.error("Batch mode requires --queue")
        run_batch(args, pipeline)
    else:
        if not args.restaurant:
            parser.error("Single mode requires --restaurant")
        if not args.url and not args.file:
            parser.error("Single mode requires --url or --file")
        run_single(args, pipeline)


if __name__ == "__main__":
    main()
