// This is a minimal JavaScript file required by Wrangler
// The actual functionality is in the Docker container

export default {
  async fetch(request, env, ctx) {
    return new Response("Agent is running. Please use API endpoints for interaction.");
  }
}; 