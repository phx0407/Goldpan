/**
 * netlify/functions/api-ask.js — Ask GoldPan™ v0.1 serverless handler
 *
 * Single-file implementation with all providers inlined.
 * Avoids Netlify module bundling issues with directory-based functions.
 *
 * Endpoint: POST /.netlify/functions/api-ask
 * Body:     JSON answer packet from buildAnswerPacket() in ask-goldpan.js
 * Response: { answer: string }
 *
 * Environment variables:
 *   LLM_PROVIDER       — "anthropic" | "mock"  (default: "mock")
 *   ANTHROPIC_API_KEY  — required if LLM_PROVIDER=anthropic
 *   ANTHROPIC_MODEL    — optional, default claude-haiku-4-5-20251001
 */

'use strict';

// ── System prompt ──────────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are Ask GoldPan™, an AI assistant that explains GoldPan's food transparency conclusions in plain language.

GoldPan canvasses restaurants, verifies ingredient disclosures from primary sources, and computes dietary conclusions using a governed rules registry. Every derived_filters conclusion in the data packet was produced by deterministic rules — not by AI inference.

Your role is to explain what GoldPan has already concluded. You are an explanation layer, not an analysis engine.

═══ EVIDENCE BOUNDARY — ABSOLUTE RULE ═══

You may ONLY answer using the GoldPan packet provided in the user message, delimited by BEGIN_GOLDPAN_PACKET and END_GOLDPAN_PACKET. Do not use outside knowledge, general nutrition knowledge, assumptions about ingredients, or model memory. Everything you know about this question comes from that packet — nothing else. If the packet does not contain enough evidence to answer the user's question, you must say so explicitly. You may not fill gaps with inference.

If the packet contains no relevant derived_filter conclusions for the user's question, respond:
"GoldPan does not have enough evidence in the current packet to answer that confidently."
You may then tell the user what kind of evidence GoldPan would need, but you must not guess or estimate.

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


// ── Providers (inlined) ────────────────────────────────────────────────────────

async function callMock(systemPrompt, userMessage) {
  await new Promise(r => setTimeout(r, 400));

  const questionMatch = userMessage.match(/User question: "(.+?)"/);
  const question = questionMatch ? questionMatch[1] : 'your question';

  const dishMatch = userMessage.match(/retrieved_dishes: (\d+)/);
  const dishCount = dishMatch ? parseInt(dishMatch[1], 10) : 0;

  if (dishCount === 0) {
    return (
      'GoldPan doesn\'t have enough verified evidence to answer "' + question + '". ' +
      'Try browsing the dish list directly using the filters above. ' +
      'For any allergy or intolerance, always confirm directly with the restaurant before ordering.'
    );
  }

  return (
    '[Ask GoldPan™ — Mock Response]\n\n' +
    'Based on current GoldPan evidence, I found ' + dishCount + ' dish(es) relevant to "' + question + '". ' +
    'GoldPan\'s analysis checks each dish\'s verified ingredient disclosures against its rules registry. ' +
    'A conclusion of "No [X] Ingredients Identified" means the verified ingredient list does not contain that item ' +
    'based on what the restaurant has publicly disclosed. ' +
    '"Unknown" means GoldPan did not have sufficient verified evidence to reach a conclusion.\n\n' +
    'To enable real AI answers: set LLM_PROVIDER=anthropic and add ANTHROPIC_API_KEY in Netlify → Site → Environment variables.\n\n' +
    'For any allergy or intolerance, always confirm directly with the restaurant before ordering.'
  );
}

async function callAnthropic(systemPrompt, userMessage, opts) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY is not set.');

  const model     = process.env.ANTHROPIC_MODEL || 'claude-haiku-4-5-20251001';
  const maxTokens = (opts && opts.maxTokens) || 600;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      system:     systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '(no body)');
    throw new Error(`Anthropic API ${response.status}: ${errText.slice(0, 200)}`);
  }

  const data = await response.json();
  const text = data.content?.[0]?.text;
  if (!text) throw new Error('Anthropic returned empty content.');
  return text;
}

function getProvider(name) {
  if (name === 'anthropic') return callAnthropic;
  return callMock;
}


// ── Packet → user message ──────────────────────────────────────────────────────

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
    lines.push('retrieved_dishes: 0');
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

function logPacketSummary(packet) {
  const dishes  = packet.retrieved_dishes || [];
  const dishIds = dishes.map(d => d.id || d.name).filter(Boolean);
  const filterIds = new Set();
  dishes.forEach(d => Object.keys(d.derived_filters || {}).forEach(s => filterIds.add(s)));

  console.log('[AskGoldPan] packet', {
    question:   packet.user_question,
    dishes:     dishIds,
    filters:    [...filterIds],
    provider:   process.env.LLM_PROVIDER || 'mock',
  });
}

function logResponseQuality(answer, packet) {
  const dishes = packet.retrieved_dishes || [];
  if (!dishes.length) return;

  const answerLower = answer.toLowerCase();
  const packetTerms = [];
  dishes.forEach(d => {
    if (d.name)       packetTerms.push(d.name.toLowerCase());
    if (d.restaurant) packetTerms.push(d.restaurant.toLowerCase());
  });

  const cited = packetTerms.some(t => t.length > 3 && answerLower.includes(t));
  const computedCount = dishes.reduce((n, d) =>
    n + Object.values(d.derived_filters || {}).filter(f => f.status === 'computed').length, 0);

  if (!cited && computedCount === 0) {
    console.warn('[AskGoldPan] BOUNDARY_WARNING', {
      question: packet.user_question,
      excerpt:  answer.slice(0, 120),
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
    return { statusCode: 400, headers: corsHeaders(), body: 'Missing user_question' };
  }

  const providerName = (process.env.LLM_PROVIDER || 'mock').toLowerCase();
  const provider     = getProvider(providerName);
  const userMessage  = buildUserMessage(packet);

  logPacketSummary(packet);

  try {
    const answer = await provider(SYSTEM_PROMPT, userMessage, { maxTokens: 600 });
    logResponseQuality(answer, packet);

    return {
      statusCode: 200,
      headers: { ...corsHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer, provider: providerName }),
    };
  } catch (err) {
    console.error(`[AskGoldPan] provider error (${providerName}):`, err.message);
    return {
      statusCode: 502,
      headers: corsHeaders(),
      body: JSON.stringify({ error: 'Ask GoldPan™ is temporarily unavailable. Please try again.' }),
    };
  }
};
