// Pyodide loader for Cloudflare Workers
// This module handles loading and initializing Pyodide

export function createPyodideLoader() {
  // We'll use this to cache the Pyodide instance
  let pyodidePromise = null;

  return async function() {
    if (!pyodidePromise) {
      // Only load Pyodide once
      pyodidePromise = (async () => {
        // Import Pyodide
        importScripts('https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js');
        
        // Initialize Pyodide
        console.log("Initializing Pyodide...");
        const pyodide = await loadPyodide({
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
      })();
    }
    
    return pyodidePromise;
  };
} 