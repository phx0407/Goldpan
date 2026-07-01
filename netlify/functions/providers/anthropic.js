/**
 * providers/anthropic.js — Ask GoldPan™ Anthropic Claude provider
 *
 * Implements the provider interface for Claude models.
 * The model and token limit are configurable via environment variables.
 *
 * Required env vars:
 *   ANTHROPIC_API_KEY   — API key from console.anthropic.com
 *
 * Optional env vars:
 *   ANTHROPIC_MODEL     — Claude model string (default: claude-haiku-4-5-20251001)
 *                         Haiku is recommended for v0.1: fast, cost-effective,
 *                         and well-suited for structured data explanation tasks.
 *                         Swap to claude-sonnet-4-6 for higher reasoning quality.
 */

'use strict';

const ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages';
const DEFAULT_MODEL     = 'claude-haiku-4-5-20251001';

/**
 * @param {string} systemPrompt  — GoldPan governed system prompt from ask.js
 * @param {string} userMessage   — formatted packet from buildUserMessage() in ask.js
 * @param {object} opts          — { maxTokens: number }
 * @returns {Promise<string>}    — answer text from Claude
 */
async function callProvider(systemPrompt, userMessage, opts = {}) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY is not set. Add it in Netlify → Site → Environment variables.');
  }

  const model     = process.env.ANTHROPIC_MODEL || DEFAULT_MODEL;
  const maxTokens = opts.maxTokens || 600;

  const response = await fetch(ANTHROPIC_API_URL, {
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
      messages: [
        { role: 'user', content: userMessage },
      ],
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '(no body)');
    throw new Error(`Anthropic API returned ${response.status}: ${errText.slice(0, 200)}`);
  }

  const data = await response.json();
  const text = data.content?.[0]?.text;

  if (!text) {
    throw new Error('Anthropic API returned an empty response content block.');
  }

  return text;
}

module.exports = { callProvider };
