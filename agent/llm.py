"""
LLM module for EigenLayer AI Agent
Provides interfaces to AI models and search functionality
"""

from typing import Dict, Optional, Any, List

class OpenRouterBackend:
    """Implementation of OpenRouter API to access multiple AI models"""
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4-turbo", tavily_api_key: Optional[str] = None, **kwargs):
        """
        Initialize OpenRouter backend
        
        Args:
            api_key: OpenRouter API key
            model: Model name to use (default: openai/gpt-4-turbo)
            tavily_api_key: Optional Tavily API key for web search capabilities
            
        Examples of models:
            - openai/gpt-4-turbo
            - openai/gpt-3.5-turbo
            - anthropic/claude-3-opus
            - anthropic/claude-3-sonnet
            - anthropic/claude-3-haiku
            - mistral/mistral-large
            - meta-llama/llama-3-70b-instruct
        """
        try:
            import requests
            import json
        except ImportError:
            raise ImportError("Requests package is not installed. Install using 'pip install requests'")
        
        self.api_key = api_key
        self.model = model
        self.tavily_api_key = tavily_api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.request_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://eigenlayer-ai-agent.com",  # Your site URL
            "X-Title": "EigenLayer AI Agent"  # Your app name
        }
    
    def generate_response(self, query: str) -> str:
        """Generate a response using OpenRouter API"""
        import requests
        import json
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": query}
            ]
        }
        
        response = requests.post(
            self.api_url,
            headers=self.request_headers,
            data=json.dumps(payload)
        )
        
        if response.status_code != 200:
            error_detail = response.json().get('error', {}).get('message', 'Unknown error')
            raise Exception(f"OpenRouter API error ({response.status_code}): {error_detail}")
        
        data = response.json()
        return data['choices'][0]['message']['content']
    
    def search_web(self, query: str) -> List[Dict[str, str]]:
        """
        Search the web for information related to the query using Tavily Search API
        
        Args:
            query: The search query
            
        Returns:
            A list of search results, each with title, content, and url keys
            
        Raises:
            Exception: If Tavily API key is not provided or the search fails
        """
        if not self.tavily_api_key:
            raise Exception("Tavily API key is required for web search. Please provide a tavily_api_key when initializing the backend.")
        
        import requests
        import json
        
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tavily_api_key}"
        }
        
        payload = {
            "query": query,
            "search_depth": "basic",
            "include_domains": [],
            "exclude_domains": [],
            "max_results": 5
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                error_detail = response.json().get('detail', 'Unknown error')
                raise Exception(f"Tavily API error ({response.status_code}): {error_detail}")
            
            data = response.json()
            results = []
            
            for result in data.get('results', []):
                results.append({
                    "title": result.get('title', ''),
                    "content": result.get('content', ''),
                    "url": result.get('url', '')
                })
            
            return results
        except Exception as e:
            raise Exception(f"Error searching with Tavily: {str(e)}")
    
    def generate_response_with_search(self, query: str) -> str:
        """
        Generate a response with web search augmentation
        
        Args:
            query: The user query
            
        Returns:
            AI response augmented with web search results
        """
        try:
            # Perform web search
            search_results = self.search_web(query)
            
            # Format search results as context
            context = "Web search results:\n\n"
            for i, result in enumerate(search_results, 1):
                context += f"{i}. {result['title']}\n"
                context += f"   {result['content'][:200]}...\n"
                context += f"   Source: {result['url']}\n\n"
            
            # Generate response with context
            import requests
            import json
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant. Answer based on the provided web search results when relevant."},
                    {"role": "user", "content": f"Here is some relevant information from the web:\n\n{context}\n\nBased on this information, please answer: {query}"}
                ]
            }
            
            response = requests.post(
                self.api_url,
                headers=self.request_headers,
                data=json.dumps(payload)
            )
            
            if response.status_code != 200:
                error_detail = response.json().get('error', {}).get('message', 'Unknown error')
                raise Exception(f"OpenRouter API error ({response.status_code}): {error_detail}")
            
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            # Fall back to regular response if search fails
            import logging
            logging.warning(f"Web search failed, falling back to standard response: {str(e)}")
            return self.generate_response(query)
    
    def list_available_models(self) -> List[str]:
        """Get a list of available models from OpenRouter"""
        import requests
        import json
        
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=self.request_headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch models: {response.status_code}")
        
        # Print the response JSON to understand its structure
        data = response.json()
        
        # Debug output to help diagnose issues
        try:
            # Check if data is a dictionary with a 'data' key (common API pattern)
            if isinstance(data, dict) and 'data' in data:
                models = data['data']
                return [model['id'] for model in models]
            # If it's a list directly
            elif isinstance(data, list):
                return [model['id'] for model in data]
            else:
                # If we don't understand the structure, print it for debugging
                # but return an empty list to avoid crashes
                print(f"Unexpected API response structure: {json.dumps(data, indent=2)}")
                return []
        except Exception as e:
            print(f"Error parsing models: {e}")
            print(f"API Response: {json.dumps(data, indent=2)}")
            raise 