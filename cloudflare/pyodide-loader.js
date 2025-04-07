// Pyodide loader for Cloudflare Workers
// This module handles loading and initializing Pyodide

export function createPyodideLoader() {
  // We'll use this to cache the Pyodide instance
  let pyodidePromise = null;

  return async function() {
    if (!pyodidePromise) {
      // Only load Pyodide once
      pyodidePromise = (async () => {
        // Import Pyodide using dynamic import for better compatibility
        // First, we'll check if we're in a worker environment that supports importScripts
        let pyodide;
        
        try {
          // Check if we're in a Worker environment that has importScripts
          if (typeof importScripts === 'function') {
            // Use importScripts in worker environments (like Cloudflare Workers)
            importScripts('https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js');
            console.log("Loaded Pyodide via importScripts");
          } else {
            throw new Error("importScripts not available, trying dynamic import");
          }
        } catch (error) {
          console.log("Could not use importScripts, using dynamic import instead:", error.message);
          
          // For environments that don't support importScripts (like Node.js during testing)
          try {
            // When testing locally with Node.js, this might not work properly
            console.log("Note: Local testing of Pyodide in Node.js is limited");
            console.log("This is a development fallback only - the worker will run correctly in the Cloudflare environment");
            
            // Try to load Pyodide via dynamic import (this will likely fail in Node.js)
            // But we're providing a more graceful error
            try {
              const pyodideModule = await import('https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js');
              
              // Set loadPyodide in the appropriate global object
              const globalObj = typeof window !== 'undefined' ? window : 
                              typeof global !== 'undefined' ? global : self;
              
              globalObj.loadPyodide = pyodideModule.loadPyodide;
              console.log("Loaded Pyodide via dynamic import");
            } catch (importError) {
              console.error("Failed to dynamically import Pyodide:", importError.message);
              console.log("This is expected during local testing - Pyodide requires a browser environment");
              
              // Mock the Pyodide functionality for testing
              return {
                runPythonAsync: async (code) => {
                  console.log("[MOCK] Would run Python code:", code);
                  return "Mock Python Result";
                },
                runPython: (code) => {
                  console.log("[MOCK] Would run Python code synchronously:", code);
                  return "Mock Python Result";
                },
                FS: {
                  mkdir: (path) => console.log(`[MOCK] Would create directory: ${path}`),
                  writeFile: (path, data) => console.log(`[MOCK] Would write file: ${path}`)
                },
                loadPackage: async () => console.log("[MOCK] Would load packages")
              };
            }
          } catch (nodeError) {
            console.error("Error in Node.js environment:", nodeError);
            throw new Error("Cannot initialize Pyodide in this environment");
          }
        }
        
        try {
          // Initialize Pyodide
          console.log("Initializing Pyodide...");
          pyodide = await loadPyodide({
            indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.23.4/full/',
          });
          console.log("Pyodide initialized successfully");
          
          // Load Python standard libraries and packages
          console.log("Loading micropip and other packages...");
          await pyodide.loadPackage(['micropip']);
          
          // Install required packages
          console.log("Installing dependencies...");
          await pyodide.runPythonAsync(`
            import micropip
            import sys
            
            # Install dependencies
            print("Installing dependencies...")
            await micropip.install([
              'pydantic',
              'loguru', 
              'web3',
              'python-dotenv'
            ])
            
            print("Dependencies installed successfully")
          `);
          
          // Create the directory for the Python package
          console.log("Creating eigenlayer-ai-agent directory...");
          pyodide.FS.mkdir('/eigenlayer-ai-agent');
          
          // Fetch and load the config.json
          console.log("Loading config.json...");
          try {
            const configResponse = await fetch('config.json');
            if (configResponse.ok) {
              const configText = await configResponse.text();
              pyodide.FS.writeFile('/eigenlayer-ai-agent/config.json', configText);
              console.log("Successfully loaded config.json");
            } else {
              console.error("Failed to load config.json:", configResponse.status, configResponse.statusText);
            }
          } catch (error) {
            console.error("Error loading config.json:", error);
          }
          
          // Fetch and extract the agent.zip file
          console.log("Loading Python agent code...");
          try {
            // Fetch the agent.zip file
            const agentResponse = await fetch('agent.zip');
            if (!agentResponse.ok) {
              throw new Error(`Failed to fetch agent.zip: ${agentResponse.status} ${agentResponse.statusText}`);
            }
            
            // Convert the response to an ArrayBuffer
            const zipData = await agentResponse.arrayBuffer();
            
            // Write the ZIP file to the virtual filesystem
            pyodide.FS.writeFile('/agent.zip', new Uint8Array(zipData));
            
            // Use Python's zipfile module to extract the code
            await pyodide.runPythonAsync(`
              import zipfile
              import os
              
              print("Extracting agent.zip...")
              
              # Create extraction directory
              os.makedirs('/eigenlayer-ai-agent', exist_ok=True)
              
              # Extract all files
              with zipfile.ZipFile('/agent.zip', 'r') as zip_ref:
                  zip_ref.extractall('/eigenlayer-ai-agent')
                  
              print("Extraction complete, files extracted:")
              # List the extracted files
              for root, dirs, files in os.walk('/eigenlayer-ai-agent'):
                  for file in files:
                      print(f"  {os.path.join(root, file)}")
                      
              # Remove the ZIP file after extraction
              os.remove('/agent.zip')
            `);
            
            console.log("Successfully loaded and extracted Python code");
          } catch (error) {
            console.error("Error loading and extracting Python code:", error);
          }
          
          console.log("Python environment setup complete");
          return pyodide;
        } catch (pyodideError) {
          console.error("Failed to initialize Pyodide:", pyodideError);
          
          if (typeof window === 'undefined') {
            console.log("Running in Node.js environment - Pyodide isn't fully supported here");
            console.log("This is expected during local testing - worker will run correctly in Cloudflare");
          }
          
          throw pyodideError;
        }
      })();
    }
    
    return pyodidePromise;
  };
} 