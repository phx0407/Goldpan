// This file is superseded by netlify/functions/ask/ (directory-based function).
// Per Netlify docs, when both ask.js and ask/index.js exist in the same
// functions directory, the directory takes precedence and this file is ignored.
// It cannot be removed from the repository via shell, so it remains as a stub.
exports.handler = async () => ({
  statusCode: 404,
  body: 'Handled by netlify/functions/ask/index.js',
});
