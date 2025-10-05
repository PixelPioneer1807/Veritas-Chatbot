# backend/web_search.py
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def search_web(query: str):
    """
    Performs a web search using the Serper API.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("SERPER_API_KEY not found in .env file.")
        return None

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        search_results = response.json()
        
        # Let's format the results to be more useful for the LLM
        formatted_results = []
        if search_results.get("organic"):
            for result in search_results["organic"]:
                formatted_results.append(f"Title: {result.get('title', 'N/A')}\nLink: {result.get('link', 'N/A')}\nSnippet: {result.get('snippet', 'N/A')}")
        
        return "\n\n---\n\n".join(formatted_results)

    except requests.exceptions.RequestException as e:
        print(f"Error during web search: {e}")
        return None