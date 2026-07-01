/**
 * providers/mock.js — Ask GoldPan™ mock LLM provider
 *
 * Returns a canned response that demonstrates the governed language patterns
 * and UI rendering without requiring an API key.
 *
 * Use for:
 *   - Local development and testing (LLM_PROVIDER=mock or unset)
 *   - Verifying UI, retrieval, and packet builder before connecting a real LLM
 *   - Confirming the governed limitations language appears correctly
 *
 * The mock response mirrors the language patterns enforced by the system prompt
 * in ask.js, so it serves as a reference for what real responses should look like.
 */

'use strict';

/**
 * @param {string} systemPrompt  — GoldPan system prompt (available for reference; mock ignores it)
 * @param {string} userMessage   — formatted packet from buildUserMessage() in ask.js
 * @param {object} opts          — { maxTokens: number }
 * @returns {Promise<string>}    — mock answer string
 */
async function callProvider(systemPrompt, userMessage, opts) {
  // Simulate a brief network delay so loading states are visible
  await delay(400);

  // Extract the question from the user message for a slightly dynamic mock
  const questionMatch = userMessage.match(/User question: "(.+?)"/);
  const question = questionMatch ? questionMatch[1] : 'your question';

  // Extract how many dishes were retrieved
  const dishMatch = userMessage.match(/Retrieved (\d+) relevant dish/);
  const dishCount = dishMatch ? parseInt(dishMatch[1], 10) : 0;

  if (dishCount === 0) {
    return (
      'GoldPan doesn\'t have enough verified evidence in its current database to answer "' + question + '". ' +
      'This could mean GoldPan hasn\'t canvassed dishes matching your criteria yet, or that evidence is still being acquired. ' +
      'Try browsing the dish list directly using the filters above. ' +
      'For any allergy or intolerance, always confirm directly with the restaurant before ordering.'
    );
  }

  return (
    '[Ask GoldPan™ Mock Response]\n\n' +
    'Based on current GoldPan evidence, I found ' + dishCount + ' dish(es) relevant to "' + question + '". ' +
    'GoldPan\'s analysis checks each dish\'s verified ingredient disclosures against its rules registry — ' +
    'a conclusion of "No [X] Ingredients Identified" means the verified ingredient list does not contain that item, ' +
    'based on what the restaurant has publicly disclosed. ' +
    '"Unknown" means GoldPan did not have sufficient verified evidence to reach a conclusion for that dish.\n\n' +
    'This is a mock response. To enable real AI answers, set LLM_PROVIDER=anthropic and add your ANTHROPIC_API_KEY ' +
    'in Netlify → Site → Environment variables.\n\n' +
    'For any allergy or intolerance, always confirm directly with the restaurant before ordering.'
  );
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = { callProvider };
