/**
 * netlify/functions/ask.js — Ask GoldPan™ v0.1 serverless handler
 *
 * Provider-agnostic. Selects an LLM provider at runtime via LLM_PROVIDER env var.
 * The system prompt and packet → message logic live here (GoldPan governance).
 * Provider implementations live in ./providers/  (retrieval, UI, and packet
 * builder are client-side in ask-goldpan.js and never touch this file).
 *
 * Environment variables:
 *   LLM_PROVIDER       — "anthropic" | "openai" | "mock"  (default: "mock")
 *   ANTHROPIC_API_KEY  — required if LLM_PROVIDER=anthropic
 *   OPENAI_API_KEY     — required if LLM_PROVIDER=openai
 *
 * Provider interface (each ./providers/*.js must export):
 *   async function callProvider(systemPrompt, userMessage, opts) → string
 *
 * Endpoint: POST /api/ask  (redirected from netlify.toml)
 * Body:     JSON answer packet from buildAnswerPacket() in ask-goldpan.js
 * Response: { answer: string }
 */

'use strict';

const path = require('path');

// ── Governed system prompt ─────────────────────────────────────────────────────
//
// This prompt enforces the GoldPan AI layer boundaries described in:
//   docs/ALLERGEN_ARCHITECTURE.md — Evidence lifecycle invariant
//   docs/RULES_REGISTRY.md        — GP-RULE-016 (Allergen Communication Rule)
//
// It is owned by GoldPan, not by any provider. Swapping providers does not
// change the governance model.

const SYSTEM_PROMPT = `You are Ask GoldPan™, an AI assistant that explains GoldPan's food transparency conclusions in plain language.

GoldPan canvasses restaurants, verifies ingredient disclosures from primary sources, and computes dietary conclusions using a governed rules registry. Every derived_filters conclusion in the data packet was produced by deterministic rules — not by AI inference.

Your role is to explain what GoldPan has already concluded. You are an explanation layer, not an analysis engine.

═══ EVIDENCE BOUNDARY — ABSOLUTE RULE ═══

You may ONLY answer using the GoldPan packet provided in the user message, delimited by BEGIN_GOLDPAN_PACKET and END_GOLDPAN_PACKET. Do not use outside knowledge, general nutrition knowledge, assumptions about ingredients, or model memory. Everything you know about this question comes from that packet — nothing else. If the packet does not contain enough evidence to answer the user's question, you must say so explicitly. You may not fill gaps with inference.

If the packet contains no relevant derived_filter conclusions for the user's question, respond:
"GoldPan does not have enough evidence in the current packet to answer that confidently."
You may then tell the user what kind of evidence GoldPan would need (e.g., "GoldPan would need verified ingredient data for this dish to compute a conclusion"), but you must not guess or estimate.

═══ WHAT YOU MAY DO ═══
- Explain GoldPan conclusions in plain, accessible language
- Summarize and compare options from the data packet
- Tell the user when GoldPan status is "unknown" and explain why (use the reasoning_summary field)
- Tell the user when GoldPan found an ingredient (status: not_applicable)
- Note when freshness status is overdue or evidence is described as insufficient
- Tell the user what evidence would be needed to answer, when the packet is insufficient

═══ WHAT YOU MUST NOT DO ═══
- Use any knowledge outside the BEGIN_GOLDPAN_PACKET / END_GOLDPAN_PACKET boundary
- Invent, infer, or assume ingredients or dietary properties not present in the packet
- Claim any dish is "safe" for an allergy or dietary restriction
- Treat "unknown" status as "probably fine," "likely safe," or "probably doesn't contain it"
- Override, reinterpret, or soften confidence or status fields
- Draw dietary conclusions from a dish name or restaurant name alone
- Reference, create, or suggest modifying GoldPan's evidence records
- Guess when the packet is silent — silence is not evidence

═══ LANGUAGE REQUIREMENTS ═══
- Frame conclusions as: "Based on current GoldPan evidence..." or "GoldPan's analysis shows..."
- For unknown status: "GoldPan could not determine this because [reason from reasoning_summary]"
- For not_applicable status: "GoldPan identified [ingredient] in this dish's verified ingredient list"
- For inferred confidence: the conclusion is based on ingredient analysis — not a certified guarantee
- For verified confidence: based on a primary verified source document
- For overdue freshness: note that menu data may not be current
- When the packet is insufficient: "GoldPan does not have enough evidence in the current packet to answer that confidently."
- ALWAYS end allergen-related answers with: "For any allergy or intolerance, always confirm directly with the restaurant before ordering."

═══ RESPONSE STYLE ═══
- Be concise and direct. 3–6 sentences per dish is appropriate.
- If multiple dishes match, describe them clearly.
- If none match with sufficient evidence, say so using the required uncertainty phrase.
- Write in natural sentences — no bullet points or headers.
- Do not expose raw field names (slug, rule_ids, status codes) to the user.`;


// ── Provider loader ────────────────────────────────────────────────────────────

function loadProvider(name) {
  const allowed = ['anthropic', 'openai', 'mock'];
  const providerName = allowed.includes(name) ? name : 'mock';
  try {
    return require(path.join(__dirname, 'providers', providerName));
  } catch (err) {
    console.error(`Failed to load provider "${providerName}":`, err.message);
    return require(path.join(__dirname, 'providers', 'mock'));
  }
}


// ── Handler ────────────────────────────────────────────────────────────────────

exports.handler = async function(event) {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: corsHeaders(), body: '' };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: corsHeaders(), body: 'Method not allowed' };
  }

  let packet;
  try {
    packet = JSON.parse(event.body || '{}');
  } catch {
    return { statusCode: 400, headers: corsHeaders(), body: 'Invalid JSON body' };
  }

  if (!packet.user_question || typeof packet.user_question !== 'string') {
    return { statusCode: 400, headers: corsHeaders(), body: 'Missing user_question in packet' };
  }

  const providerName = (process.env.LLM_PROVIDER || 'mock').toLowerCase();
  const provider     = loadProvider(providerName);
  const userMessage  = buildUserMessage(packet);

  // ── Dev logging ──────────────────────────────────────────────────────────────
  logPacketSummary(packet);

  try {
    const answer = await provider.callProvider(SYSTEM_PROMPT, userMessage, {
      maxTokens: 600,
    });

    // Warn when the response doesn't cite any dish or filter from the packet —
    // a signal the model may have answered from outside the packet boundary.
    logResponseQuality(answer, packet);

    return {
      statusCode: 200,
      headers: { ...corsHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer, provider: providerName }),
    };
  } catch (err) {
    console.error(`Provider "${providerName}" error:`, err.message || err);
    return {
      statusCode: 502,
      headers: corsHeaders(),
      body: JSON.stringify({ error: 'Ask GoldPan™ is temporarily unavailable. Please try again.' }),
    };
  }
};


// ── Packet → user message ──────────────────────────────────────────────────────
//
// Converts the structured answer packet into a plain-text user message for
// the LLM. The packet content is wrapped in BEGIN_GOLDPAN_PACKET /
// END_GOLDPAN_PACKET markers so the system prompt can cite an unambiguous
// boundary. Only content inside those markers is usable evidence.
//
// This is GoldPan governance logic — it belongs here, not in any provider.

function buildUserMessage(packet) {
  const lines = [];

  lines.push(`User question: "${packet.user_question}"`);
  lines.push('');
  lines.push('The following GoldPan evidence packet is the ONLY source you may use to answer. Do not use any knowledge outside this boundary.');
  lines.push('');
  lines.push('BEGIN_GOLDPAN_PACKET');
  lines.push(`database_size: ${packet.total_dishes_in_db || 'unknown'} dishes`);
  lines.push(`relevant_filters_checked: ${(packet.relevant_filter_slugs || []).join(', ')}`);
  lines.push(`evidence_note: ${packet.evidence_note || ''}`);
  lines.push('');

  const dishes = packet.retrieved_dishes || [];

  if (dishes.length === 0) {
    lines.push('retrieved_dishes: none');
    lines.push('No matching dishes were found in GoldPan for this query.');
  } else {
    lines.push(`retrieved_dishes: ${dishes.length}`);
    lines.push('');

    dishes.forEach((dish, i) => {
      lines.push(`[Dish ${i + 1}] id=${dish.id}  name="${dish.name}"  restaurant="${dish.restaurant}"  location="${dish.location || 'unknown'}"`);

      if (dish.tags && dish.tags.length > 0) {
        lines.push(`  dietary_tags: ${dish.tags.join(', ')}`);
      }

      const f = dish.freshness || {};
      if (f.recanvass_status && f.recanvass_status !== 'unknown') {
        lines.push(`  freshness: recanvass_status=${f.recanvass_status}, last_canvassed=${f.last_canvassed || 'unknown'}`);
      }

      const filters = dish.derived_filters || {};
      const filterKeys = Object.keys(filters);

      if (filterKeys.length === 0) {
        lines.push('  derived_filters: none');
      } else {
        filterKeys.forEach(slug => {
          const fc = filters[slug];
          lines.push(`  filter[${slug}]:`);
          lines.push(`    conclusion=${fc.conclusion}`);
          lines.push(`    status=${fc.status}`);
          lines.push(`    confidence=${fc.confidence}`);
          if (fc.reasoning_summary) lines.push(`    reasoning=${fc.reasoning_summary}`);
          if (fc.limitations)       lines.push(`    limitations=${fc.limitations}`);
        });
      }
      lines.push('');
    });
  }

  lines.push('END_GOLDPAN_PACKET');
  lines.push('');
  lines.push('Answer the user question using only the evidence above. If the packet does not support an answer, say so using the required uncertainty phrase.');

  return lines.join('\n');
}


// ── Dev logging ────────────────────────────────────────────────────────────────

/**
 * Log a summary of the incoming packet for debugging retrieval quality.
 * Shows dish IDs and the filter slugs present in each dish.
 */
function logPacketSummary(packet) {
  const dishes  = packet.retrieved_dishes || [];
  const dishIds = dishes.map(d => d.id || d.name).filter(Boolean);

  const filterIds = new Set();
  dishes.forEach(d => {
    Object.keys(d.derived_filters || {}).forEach(slug => filterIds.add(slug));
  });

  console.log('[AskGoldPan] packet summary', {
    question:       packet.user_question,
    dish_count:     dishes.length,
    dish_ids:       dishIds,
    filter_ids:     [...filterIds],
    relevant_slugs: packet.relevant_filter_slugs || [],
    provider:       process.env.LLM_PROVIDER || 'mock',
  });
}

/**
 * Warn when the model's response doesn't reference any dish name, restaurant,
 * or filter conclusion from the packet — a signal the model may have answered
 * from general knowledge outside the packet boundary.
 *
 * This is a heuristic check for dev/review purposes; it doesn't block the
 * response. Log entries with [AskGoldPan] BOUNDARY_WARNING should be reviewed.
 */
function logResponseQuality(answer, packet) {
  const dishes = packet.retrieved_dishes || [];
  if (dishes.length === 0) return; // no packet evidence to check against

  const answerLower = answer.toLowerCase();

  // Check if any dish name or restaurant from the packet appears in the response
  const packetTerms = [];
  dishes.forEach(d => {
    if (d.name)       packetTerms.push(d.name.toLowerCase());
    if (d.restaurant) packetTerms.push(d.restaurant.toLowerCase());
  });

  const citesPacked = packetTerms.some(term => term.length > 3 && answerLower.includes(term));

  // Also check for the required uncertainty phrase if evidence is thin
  const computedCount = dishes.reduce((n, d) => {
    return n + Object.values(d.derived_filters || {}).filter(f => f.status === 'computed').length;
  }, 0);

  if (!citesPacked && computedCount === 0) {
    console.warn('[AskGoldPan] BOUNDARY_WARNING: response does not appear to reference packet evidence', {
      question:        packet.user_question,
      computed_filters: computedCount,
      response_excerpt: answer.slice(0, 120),
    });
  } else {
    console.log('[AskGoldPan] response quality OK', {
      cites_packet: citesPacked,
      computed_filters: computedCount,
    });
  }
}


// ── CORS ───────────────────────────────────────────────────────────────────────

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
  };
}
