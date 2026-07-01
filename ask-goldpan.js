/**
 * ask-goldpan.js — Ask GoldPan™ v0.1
 * Client-side module: retrieval, packet builder, UI, response renderer.
 *
 * Architecture:
 *   User question
 *     → retrieveRelevantDishes()   — searches in-memory dish array
 *     → buildAnswerPacket()        — assembles governed data for LLM
 *     → POST /api/ask             — serverless proxy calls Claude
 *     → renderAGResponse()         — displays governed answer
 *
 * This module never sends raw dishes.json to the LLM.
 * It builds a minimal structured packet from verified GoldPan conclusions.
 *
 * Setup: set window.AG_ENDPOINT to your serverless proxy URL.
 * Default: '/api/ask'  (works with netlify/functions/ask.js)
 */

// ── Configuration ──────────────────────────────────────────────────────────────

window.AG_ENDPOINT = window.AG_ENDPOINT || '/.netlify/functions/ask';

// ── Dietary keyword map ────────────────────────────────────────────────────────
// Maps question keywords → filter slugs in derived_filters

const KEYWORD_TO_FILTER = {
  // Dietary
  'beef':        'no-beef-identified',
  'red meat':    'no-beef-identified',
  'steak':       'no-beef-identified',
  'pork':        'no-pork-identified',
  'bacon':       'no-pork-identified',
  'ham':         'no-pork-identified',
  // Allergens
  'wheat':       'no-wheat-ingredients-identified',
  'gluten':      'no-wheat-ingredients-identified',
  'milk':        'no-milk-ingredients-identified',
  'dairy':       'no-milk-ingredients-identified',
  'egg':         'no-egg-ingredients-identified',
  'eggs':        'no-egg-ingredients-identified',
  'soy':         'no-soy-ingredients-identified',
  'soybean':     'no-soy-ingredients-identified',
  'sesame':      'no-sesame-ingredients-identified',
  'peanut':      'no-peanut-ingredients-identified',
  'peanuts':     'no-peanut-ingredients-identified',
  'tree nut':    'no-tree-nut-ingredients-identified',
  'tree nuts':   'no-tree-nut-ingredients-identified',
  'nut':         'no-tree-nut-ingredients-identified',
  'fish':        'no-fish-ingredients-identified',
  'shellfish':   'no-shellfish-ingredients-identified',
  'shrimp':      'no-shellfish-ingredients-identified',
  'crab':        'no-shellfish-ingredients-identified',
  'lobster':     'no-shellfish-ingredients-identified',
};

// Dietary tag keywords that match the tags array on each dish
const KEYWORD_TO_TAG = {
  'vegan':        'vegan',
  'vegetarian':   'vegetarian',
  'gluten-free':  'gluten-free',
  'gluten free':  'gluten-free',
  'dairy-free':   'dairy-free',
  'dairy free':   'dairy-free',
  'high protein': 'high-protein',
  'high-protein': 'high-protein',
  'halal':        'halal',
  'kosher':       'kosher',
};


// ── Retrieval ──────────────────────────────────────────────────────────────────

/**
 * Detect which filter slugs and tags are relevant to the user's question.
 * Returns { filters: Set<string>, tags: Set<string> }
 */
function detectIntent(question) {
  const q = question.toLowerCase();
  const filters = new Set();
  const tags = new Set();

  for (const [kw, slug] of Object.entries(KEYWORD_TO_FILTER)) {
    if (q.includes(kw)) filters.add(slug);
  }
  for (const [kw, tag] of Object.entries(KEYWORD_TO_TAG)) {
    if (q.includes(kw)) tags.add(tag);
  }

  return { filters, tags };
}

/**
 * Score one dish for relevance to the question.
 * Higher = more relevant.
 */
function scoreDish(dish, q, intent) {
  let score = 0;
  const ql = q.toLowerCase();
  const nameLower = (dish.name || '').toLowerCase();
  const restLower = (dish.restaurant || '').toLowerCase();
  const tags = dish.tags || [];
  const df = dish.derived_filters || {};

  // Restaurant name match
  if (restLower && ql.includes(restLower)) score += 4;

  // Dish name keyword overlap
  if (nameLower && ql.split(/\s+/).some(w => w.length > 3 && nameLower.includes(w))) score += 2;

  // Tag match
  for (const tag of intent.tags) {
    if (tags.includes(tag)) score += 3;
  }

  // Derived filter match: computed conclusions for detected filters score highest
  for (const slug of intent.filters) {
    const fc = df[slug];
    if (!fc) continue;
    if (fc.status === 'computed') score += 4;
    else if (fc.status === 'not_applicable') score += 1; // dish has the thing but still relevant
    // unknown: +0 (not helpful)
  }

  // If no specific intent detected, boost dishes with more computed conclusions
  if (intent.filters.size === 0 && intent.tags.size === 0) {
    const computedCount = Object.values(df).filter(f => f.status === 'computed').length;
    score += computedCount;
  }

  return score;
}

/**
 * Retrieve the top N most relevant dishes for the user's question.
 * Returns an array of dish objects.
 */
function retrieveRelevantDishes(question, allDishes, topN = 8) {
  if (!allDishes || allDishes.length === 0) return [];
  const intent = detectIntent(question);

  const scored = allDishes.map(d => ({
    dish: d,
    score: scoreDish(d, question, intent),
  }));

  scored.sort((a, b) => b.score - a.score);

  // Only include dishes with score > 0, unless nothing matched
  const relevant = scored.filter(x => x.score > 0).slice(0, topN);
  if (relevant.length === 0) {
    // Fall back to a broad sample (highest computed filter count)
    return scored.slice(0, topN).map(x => x.dish);
  }
  return relevant.map(x => x.dish);
}


// ── Packet builder ─────────────────────────────────────────────────────────────

/**
 * Build the structured answer packet sent to the LLM.
 * Only includes governed conclusions — never raw ingredient lists or unverified data.
 */
function buildAnswerPacket(question, matchedDishes) {
  const intent = detectIntent(question);

  // Determine which filter slugs to include (all detected, or all if none detected)
  const allSlugs = new Set([
    'no-beef-identified',
    'no-pork-identified',
    'no-wheat-ingredients-identified',
    'no-milk-ingredients-identified',
    'no-egg-ingredients-identified',
    'no-soy-ingredients-identified',
    'no-sesame-ingredients-identified',
    'no-peanut-ingredients-identified',
    'no-tree-nut-ingredients-identified',
    'no-fish-ingredients-identified',
    'no-shellfish-ingredients-identified',
  ]);

  const relevantSlugs = intent.filters.size > 0 ? intent.filters : allSlugs;

  const dishPackets = matchedDishes.map(dish => {
    const df = dish.derived_filters || {};
    const filteredDF = {};

    for (const slug of relevantSlugs) {
      const fc = df[slug];
      if (!fc) continue;
      // Include only the fields the LLM needs; trim long reasoning to save tokens
      filteredDF[slug] = {
        conclusion:  fc.conclusion,
        status:      fc.status,
        confidence:  fc.confidence,
        // Trim reasoning to first 250 chars to keep packet size manageable
        reasoning_summary: (fc.reasoning || '').slice(0, 250) + (fc.reasoning && fc.reasoning.length > 250 ? '…' : ''),
        limitations: (fc.limitations || '').slice(0, 200) + (fc.limitations && fc.limitations.length > 200 ? '…' : ''),
        rule_ids:    fc.rule_ids || [],
      };
    }

    // Freshness context
    const freshness = dish.freshness || {};

    return {
      id:          dish.id,
      name:        dish.name,
      restaurant:  dish.restaurant,
      location:    dish.location,
      tags:        dish.tags || [],
      derived_filters: filteredDF,
      freshness: {
        recanvass_status:    freshness.recanvass_status    || 'unknown',
        last_canvassed:      freshness.last_canvassed      || null,
        source_check_status: freshness.source_check_status || 'unknown',
      },
    };
  });

  return {
    user_question:          question,
    retrieved_dishes:       dishPackets,
    relevant_filter_slugs:  [...relevantSlugs],
    total_dishes_in_db:     window._gpDishCount || dishPackets.length,
    evidence_note:          (
      'All derived_filter conclusions were computed by GoldPan\'s deterministic rules engine. ' +
      'status=computed means a conclusion was reached. status=unknown means insufficient evidence. ' +
      'status=not_applicable means the ingredient was found (filter does not apply). ' +
      'confidence=inferred means based on disclosed ingredient analysis; verified means confirmed source.'
    ),
  };
}


// ── API call ───────────────────────────────────────────────────────────────────

/**
 * Send the answer packet to the serverless proxy and return the LLM response.
 * Throws on network/API errors.
 */
async function callAskGoldPan(packet) {
  const resp = await fetch(window.AG_ENDPOINT, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(packet),
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => 'Unknown error');
    throw new Error(`Ask GoldPan API error (${resp.status}): ${err}`);
  }

  const data = await resp.json();
  return data.answer || data.response || data.content || '(no response)';
}


// ── UI ─────────────────────────────────────────────────────────────────────────

/**
 * Inject the Ask GoldPan™ UI block into the page.
 * Call after DOMContentLoaded. targetSelector is a CSS selector for the
 * element to insert before (default: the search bar).
 */
function injectAskGoldPanUI(targetSelector) {
  if (document.getElementById('ag-section')) return; // already injected
  targetSelector = targetSelector || '.search-bar';
  const target = document.querySelector(targetSelector);
  if (!target) return;

  const wrap = document.createElement('div');
  wrap.id = 'ag-section';
  wrap.innerHTML = `
    <div id="ag-bar">
      <span class="ag-label">Ask GoldPan™</span>
      <div class="ag-input-row">
        <input
          id="ag-input"
          class="ag-input"
          type="text"
          placeholder="e.g. Which dishes don't have beef? What's vegan at Slutty Vegan?"
          autocomplete="off"
        />
        <button id="ag-submit" class="ag-btn" onclick="askGoldPan()">Ask</button>
      </div>
      <p class="ag-disclaimer">Ask GoldPan™ explains GoldPan's verified data. It does not provide allergy safety advice. Always confirm with the restaurant.</p>
    </div>
    <div id="ag-response" class="ag-response" style="display:none;">
      <div class="ag-response-header">
        <span class="ag-response-label">Ask GoldPan™</span>
        <button class="ag-response-close" onclick="closeAGResponse()">✕</button>
      </div>
      <div id="ag-response-body" class="ag-response-body"></div>
    </div>
  `;

  target.parentNode.insertBefore(wrap, target);

  // Allow Enter key to submit
  document.getElementById('ag-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') askGoldPan();
  });
}

/**
 * Main entry point. Called by the Ask button and Enter key.
 */
async function askGoldPan() {
  const input = document.getElementById('ag-input');
  const question = (input ? input.value : '').trim();
  if (!question) return;

  const btn = document.getElementById('ag-submit');
  const responseEl = document.getElementById('ag-response');
  const bodyEl = document.getElementById('ag-response-body');

  // Loading state
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  if (responseEl) responseEl.style.display = 'block';
  if (bodyEl) bodyEl.innerHTML = '<span class="ag-loading">Searching GoldPan data…</span>';

  try {
    // Use dishes already loaded in the discover app (window var set by discover/index.html)
    const allDishes = window.dishes || [];
    if (window._gpDishCount === undefined) window._gpDishCount = allDishes.length;

    const matched   = retrieveRelevantDishes(question, allDishes, 8);
    const packet    = buildAnswerPacket(question, matched);
    const answer    = await callAskGoldPan(packet);

    renderAGResponse(answer, matched);
  } catch (err) {
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="ag-error">
          <strong>Ask GoldPan™ is unavailable.</strong><br />
          ${escHtml(err.message || 'Please try again.')}
        </div>
      `;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Ask'; }
  }
}

/**
 * Render the LLM response and the matched dish chips below it.
 */
function renderAGResponse(answer, matchedDishes) {
  const bodyEl = document.getElementById('ag-response-body');
  if (!bodyEl) return;

  // Convert newlines to <br> and escape HTML
  const formatted = escHtml(answer).replace(/\n/g, '<br />');

  // Matched dish chips for context transparency
  const dishChips = matchedDishes.map(d =>
    `<span class="ag-dish-chip">${escHtml(d.name)} <span class="ag-chip-rest">· ${escHtml(d.restaurant)}</span></span>`
  ).join('');

  bodyEl.innerHTML = `
    <div class="ag-answer-text">${formatted}</div>
    ${matchedDishes.length > 0 ? `
      <div class="ag-context-label">GoldPan data consulted:</div>
      <div class="ag-dish-chips">${dishChips}</div>
    ` : ''}
  `;
}

function closeAGResponse() {
  const el = document.getElementById('ag-response');
  if (el) el.style.display = 'none';
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ── CSS ────────────────────────────────────────────────────────────────────────

/**
 * Inject Ask GoldPan™ styles. Call once, early in page load.
 */
function injectAskGoldPanStyles() {
  if (document.getElementById('ag-styles')) return;
  const style = document.createElement('style');
  style.id = 'ag-styles';
  style.textContent = `
    #ag-section { border-bottom: 1px solid #1A1A1A; }

    #ag-bar {
      padding: 20px 48px 16px;
      background: #0D0D0D;
      border-bottom: 1px solid rgba(201,168,76,0.10);
    }
    @media (max-width: 768px) { #ag-bar { padding: 16px 20px 14px; } }

    .ag-label {
      display: block;
      font-family: 'DM Mono', monospace;
      font-size: 10px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: #C9A84C;
      margin-bottom: 10px;
    }

    .ag-input-row {
      display: flex;
      gap: 0;
      max-width: 720px;
    }

    .ag-input {
      flex: 1;
      background: #1A1A1A;
      border: 1px solid #2A2A2A;
      border-right: none;
      color: #F5F2EC;
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      padding: 13px 18px;
      outline: none;
      transition: border-color 0.2s;
    }
    .ag-input::placeholder { color: #555550; }
    .ag-input:focus { border-color: rgba(201,168,76,0.5); }

    .ag-btn {
      background: #C9A84C;
      color: #0A0A0A;
      border: none;
      padding: 13px 26px;
      font-family: 'DM Sans', sans-serif;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      cursor: pointer;
      transition: background 0.2s;
      white-space: nowrap;
    }
    .ag-btn:hover { background: #E8C97A; }
    .ag-btn:disabled { background: #555550; cursor: wait; }

    .ag-disclaimer {
      margin-top: 8px;
      font-size: 10px;
      color: #444440;
      letter-spacing: 0.03em;
      max-width: 720px;
    }

    .ag-response {
      background: #0F0F0F;
      border-bottom: 1px solid rgba(201,168,76,0.15);
    }

    .ag-response-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 48px 0;
    }
    @media (max-width: 768px) { .ag-response-header { padding: 12px 20px 0; } }

    .ag-response-label {
      font-family: 'DM Mono', monospace;
      font-size: 10px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: rgba(201,168,76,0.6);
    }

    .ag-response-close {
      background: none;
      border: none;
      color: #555550;
      font-size: 16px;
      cursor: pointer;
      padding: 0 4px;
      line-height: 1;
      transition: color 0.2s;
    }
    .ag-response-close:hover { color: #C9A84C; }

    .ag-response-body {
      padding: 14px 48px 20px;
      max-width: 760px;
    }
    @media (max-width: 768px) { .ag-response-body { padding: 12px 20px 16px; } }

    .ag-loading {
      font-family: 'DM Mono', monospace;
      font-size: 12px;
      color: #555550;
      letter-spacing: 0.1em;
    }

    .ag-answer-text {
      font-size: 14px;
      line-height: 1.7;
      color: #D8D4CC;
      margin-bottom: 16px;
    }

    .ag-error {
      font-size: 13px;
      color: #C94C4C;
      line-height: 1.6;
    }

    .ag-context-label {
      font-family: 'DM Mono', monospace;
      font-size: 10px;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: #444440;
      margin-bottom: 8px;
    }

    .ag-dish-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .ag-dish-chip {
      font-size: 11px;
      padding: 4px 10px;
      background: #1A1A1A;
      border: 1px solid #2A2A2A;
      color: #9A9488;
    }

    .ag-chip-rest {
      color: #444440;
    }
  `;
  document.head.appendChild(style);
}
