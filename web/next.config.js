/** @type {import('next').NextConfig} */
const nextConfig = {
  // GOLDPAN_API_URL and ADMIN_API_KEY are server-only env vars.
  // Never prefix with NEXT_PUBLIC_ — they must not reach the browser.
};

module.exports = nextConfig;
