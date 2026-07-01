/**
 * providers/openai.js — Ask GoldPan™ OpenAI provider (stub)
 *
 * Implements the provider interface for OpenAI models (GPT-4o, etc.).
 * Not yet activated — provided so swapping to OpenAI requires only:
 *   1. Set LLM_PROVIDER=openai
 *   2. Set OPENAI_API_KEY
 *   3. No changes to ask.js, retrieval, packet builder, or UI
 *
 * Required env vars (when LLM_PROVIDER=openai):
 *   OPENAI_API_KEY   — API key from platform.openai.com
 *
 * Optional env vars:
 *   OPENAI_MODEL     — model string (default: gpt-4o-mini)
 */

'use strict';

const OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions';
const DEFAULT_MODEL  = 'gpt-4o-mini';

/**
 * @param {string} systemPrompt  — GoldPan governed system prompt from ask.js
 * @param {string} userMessage   — formatted packet from buildUserMessage() in ask.js
 * @param {object} opts          — { maxTokens: number }
 * @returns {Promise<string>}    — answer text from OpenAI
 */
async function callProvider(systemPrompt, userMessage, opts = {}) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is not set. Add it in Netlify → Site → Environment variables.');
  }

  const model     = process.env.OPENAI_MODEL || DEFAULT_MODEL;
  const maxTokens = opts.maxTokens || 600;

  const response = await fetch(OPENAI_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      messages: [
        { role: 'system',  content: systemPrompt },
        { role: 'user',    content: userMessage  },
      ],
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '(no body)');
    throw new Error(`OpenAI API returned ${response.status}: ${errText.slice(0, 200)}`);
  }

  const data = await response.json();
  const text = data.choices?.[0]?.message?.content;

  if (!text) {
    throw new Error('OpenAI API returned an empty choices array.');
  }

  return text;
}

module.exports = { callProvider };
