// Main Worker file that uses Pyodide to run Python code
import { createPyodideLoader } from './pyodide-loader.js';

// Initialize Pyodide asynchronously
const initPyodide = createPyodideLoader();

export default {
  // This is called for HTTP requests - provides status and manual control
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const path = url.pathname;
      
      // Status endpoint - just returns status information
      if (path === "/" || path === "/status") {
        return new Response(JSON.stringify({
          status: "running",
          message: "Agent is running on a schedule",
          last_run: env.LAST_RUN || "No runs recorded yet"
        }), {
          status: 200,
          headers: {'Content-Type': 'application/json'}
        });
      }
      
      // Manual trigger endpoint - allows manually triggering the agent
      if (path === "/run") {
        // Queue the agent to run (non-blocking)
        ctx.waitUntil(runAgent(env, ctx));
        
        return new Response(JSON.stringify({
          status: "triggered",
          message: "Agent run has been triggered"
        }), {
          status: 200,
          headers: {'Content-Type': 'application/json'}
        });
      }
      
      return new Response(JSON.stringify({
        error: "Unknown endpoint",
        message: "Available endpoints: /, /status, /run"
      }), {
        status: 404,
        headers: {'Content-Type': 'application/json'}
      });
    } catch (error) {
      console.error('Error in fetch handler:', error);
      return new Response(JSON.stringify({
        error: error.message,
        stack: error.stack
      }), {
        status: 500,
        headers: {'Content-Type': 'application/json'}
      });
    }
  },
  
  // This is called automatically on the defined schedule
  async scheduled(event, env, ctx) {
    console.log(`Running scheduled agent at ${new Date().toISOString()}`);
    ctx.waitUntil(runAgent(env, ctx));
  }
};

// Function to run the Python agent
async function runAgent(env, ctx) {
  try {
    console.log("Initializing Pyodide and running agent...");
    
    // Initialize Pyodide
    const pyodide = await initPyodide();
    
    // Set up environment variables for Python code
    await pyodide.runPythonAsync(`
      import os
      import sys
      
      # Set environment variables from Cloudflare secrets
      os.environ["API_KEY"] = "${env.API_KEY || ""}"
      os.environ["AGENT_PRIVATE_KEY"] = "${env.AGENT_PRIVATE_KEY || ""}"
      
      # Set up sys.path and change directory
      sys.path.append('/eigenlayer-ai-agent')
      os.chdir('/eigenlayer-ai-agent')
      
      # Redirect stdout to capture output
      import io
      sys.stdout = io.StringIO()
      sys.stderr = io.StringIO()
    `);
    
    // Run the agent's main function with --run-once flag
    // This is better for Cloudflare Workers due to the 30-60 second execution time limit
    console.log("Starting agent main function with --run-once...");
    await pyodide.runPythonAsync(`
      import sys
      from agent.__main__ import main
      
      # Patch the arguments to simulate command line arguments
      # Using --run-once to ensure the agent completes within the time limit
      sys.argv = ['agent', '--run-once', '--config', 'config.json']
      
      # Execute the main function
      main()
    `);
    
    // Get the output from Python
    const stdout = pyodide.runPython('sys.stdout.getvalue()');
    console.log("Python stdout:", stdout);
    
    const stderr = pyodide.runPython('sys.stderr.getvalue()');
    if (stderr.trim()) {
      console.warn("Python stderr:", stderr);
    }
    
    // Store the last run timestamp
    env.LAST_RUN = new Date().toISOString();
    
    console.log("Agent execution completed");
    return true;
  } catch (error) {
    console.error("Error running agent:", error);
    return false;
  }
} 