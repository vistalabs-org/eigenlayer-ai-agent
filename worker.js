// Cloudflare Worker entry point for EigenLayer AI Agent

// Create KV namespace binding dynamically from environment variable
let AGENT_STORAGE;

// Setup environment during initialization
async function setupEnvironment() {
  try {
    // Get KV namespace binding from environment variable
    const namespaceId = env.KV_NAMESPACE_ID;
    if (namespaceId) {
      AGENT_STORAGE = await caches.default.get(namespaceId);
    } else {
      console.error('No KV namespace ID found in environment variables');
    }
  } catch (error) {
    console.error('Error setting up environment:', error);
  }
}

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

// Handle scheduled events (cron triggers)
addEventListener('scheduled', event => {
  event.waitUntil(handleScheduled(event));
});

// Process HTTP requests
async function handleRequest(request) {
  // Setup environment if not already done
  if (!AGENT_STORAGE) {
    await setupEnvironment();
  }
  
  const url = new URL(request.url);
  
  // Health check endpoint
  if (url.pathname === '/health') {
    return new Response(JSON.stringify({ status: 'ok' }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // Status endpoint
  if (url.pathname === '/status') {
    const status = await getAgentStatus();
    return new Response(JSON.stringify(status), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // API endpoints can be added here
  
  // Default response
  return new Response('EigenLayer AI Agent running', {
    headers: { 'Content-Type': 'text/plain' }
  });
}

// Handle scheduled runs
async function handleScheduled(event) {
  console.log('Running scheduled task');
  
  // Setup environment if not already done
  if (!AGENT_STORAGE) {
    await setupEnvironment();
  }
  
  try {
    // Check for pending tasks
    const result = await processPendingTasks();
    console.log('Task processing complete:', result);
  } catch (error) {
    console.error('Error processing tasks:', error);
  }
}

// Process pending tasks
async function processPendingTasks() {
  // Access environment variables directly
  const rpcUrl = env.RPC_URL || 'http://localhost:8545';
  const model = env.MODEL || 'openai/gpt-4-turbo';
  const apiKey = env.API_KEY;
  const privateKey = env.PRIVATE_KEY;
  
  console.log(`Processing tasks with RPC URL: ${rpcUrl}`);
  console.log(`Using model: ${model}`);
  
  // This would normally call the container to process tasks
  // For Cloudflare, this would need to be implemented as HTTP requests to the container
  // The container URL would be configured in the Cloudflare dashboard or stored in KV
  
  try {
    // Store run metadata if KV is available
    if (AGENT_STORAGE) {
      await AGENT_STORAGE.put('last_run', new Date().toISOString());
    } else {
      console.warn('KV storage not available, skipping state persistence');
    }
  } catch (error) {
    console.error('Error storing run metadata:', error);
  }
  
  return { success: true };
}

// Get agent status
async function getAgentStatus() {
  let lastRun = 'Never';
  
  try {
    // Get last run time from KV if available
    if (AGENT_STORAGE) {
      lastRun = await AGENT_STORAGE.get('last_run') || 'Never';
    }
  } catch (error) {
    console.error('Error retrieving agent status:', error);
  }
  
  return {
    lastRun,
    version: '0.1.0',
    environment: 'cloudflare-workers',
    model: env.MODEL || 'unknown',
    rpcConfigured: !!env.RPC_URL
  };
} 