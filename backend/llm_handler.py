# backend/llm_handler.py
import os
from groq import Groq
from dotenv import load_dotenv
import re

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

def is_casual_conversation(query: str) -> tuple[bool, str]:
    """
    Detects if the query is casual conversation and returns appropriate response.
    Returns: (is_casual, response_text or None)
    """
    query_lower = query.lower().strip()
    
    # Greetings
    greetings = ['hi', 'hello', 'hey', 'hii', 'hola', 'greetings', 'good morning', 
                 'good afternoon', 'good evening', 'yo', 'sup', "what's up", 'whats up']
    if any(query_lower == greeting or query_lower.startswith(greeting + ' ') for greeting in greetings):
        return True, "Hello! 👋 I'm Veritas, your document analysis assistant. I'm here to help you understand and analyze your documents. Upload a PDF and ask me anything about it!"
    
    # Farewells
    farewells = ['bye', 'goodbye', 'see you', 'see ya', 'farewell', 'catch you later', 
                 'talk to you later', 'ttyl', 'take care', 'gotta go', 'gtg']
    if any(query_lower == farewell or query_lower.startswith(farewell) for farewell in farewells):
        return True, "Goodbye! 👋 Feel free to come back anytime you need help with document analysis. Have a great day!"
    
    # Thank you
    thanks = ['thank', 'thanks', 'thx', 'ty', 'appreciate', 'grateful']
    if any(thank in query_lower for thank in thanks):
        return True, "You're welcome! 😊 Happy to help! Let me know if you have any other questions about your document."
    
    # How are you
    how_are_you = ['how are you', 'how r u', 'how are u', "how's it going", 
                   'hows it going', 'what\'s up', 'whats up', 'how do you do']
    if any(phrase in query_lower for phrase in how_are_you):
        return True, "I'm doing great, thank you for asking! 😊 I'm ready to help you analyze documents. Do you have a document you'd like to explore?"
    
    # Who are you / What are you
    identity = ['who are you', 'what are you', 'tell me about yourself', 
                'who r u', 'what r u', 'your name']
    if any(phrase in query_lower for phrase in identity):
        return True, "I'm Veritas, an AI-powered document analysis assistant! 🤖 I can help you:\n• Extract information from PDF documents\n• Analyze charts and visual content\n• Search the web for additional context\n• Answer questions about your uploaded documents\n\nJust upload a document and ask away!"
    
    # Help requests
    help_requests = ['help', 'what can you do', 'how to use', 'how do i', 'capabilities']
    if any(phrase in query_lower for phrase in help_requests):
        return True, "I'd be happy to help! 💡 Here's what I can do:\n\n1. 📄 **Document Analysis**: Upload a PDF and ask questions about its content\n2. 📊 **Chart Understanding**: I can analyze graphs, charts, and visual elements\n3. 🌐 **Web Search**: Enable web search for broader context\n4. 🎤 **Voice Input**: Use the microphone for hands-free queries\n\nTry uploading a document and asking me something like:\n• 'What is this document about?'\n• 'Summarize page 5'\n• 'Explain the chart on page 3'"
    
    # OK/Okay acknowledgments
    acknowledgments = ['ok', 'okay', 'cool', 'nice', 'alright', 'got it', 'k', 'kk']
    if query_lower in acknowledgments:
        return True, "Great! 👍 Let me know if you need anything else!"
    
    return False, None

def get_chat_response(query: str, context: str):
    """
    Generates a response from the LLM based on the user's query and retrieved context.
    """
    
    # First, check if it's casual conversation
    is_casual, casual_response = is_casual_conversation(query)
    if is_casual:
        return casual_response
    
    # Check if context is essentially empty or very short
    context_has_content = context and len(context.strip()) > 50
    
    # Updated prompt to be more conversational and context-aware
    system_prompt = (
        "You are Veritas, a friendly and intelligent document analysis assistant. "
        "Your personality is helpful, clear, and conversational.\n\n"
        
        "The context may include:\n"
        "1. 'Document Context': Text extracted directly from the document.\n"
        "2. 'Visual Context': Information extracted from visual elements (charts, graphs, images).\n"
        "3. 'Web Search Results': Snippets from a web search.\n\n"
        
        "Important instructions:\n"
        "- Be conversational and friendly in your responses\n"
        "- Synthesize information from all available contexts to provide a comprehensive answer\n"
        "- If information from the document and web search results differ, prioritize the document's content but note the discrepancy\n"
        "- Answer questions directly and concisely\n"
        "- When information comes from visual content, mention that (e.g., 'According to the chart on page 3...')\n"
        "- If the answer requires information from both text and visuals, synthesize them clearly\n"
        "- If the context doesn't contain relevant information, politely say: "
        "'I couldn't find that information in your document. Would you like me to search the web?' "
        "or if web search is enabled: 'I couldn't find that in your document, but here's what I found online...'\n"
        "- Be specific and cite page numbers when relevant\n"
        "- If the user asks something very general (like 'tell me about this document'), provide a helpful summary\n"
        "- Use emojis occasionally to be more engaging, but don't overdo it\n"
    )
    
    user_prompt = f"Context:\n{context}\n\nQuestion:\n{query}"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,  # Slightly higher for more natural conversation
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error getting response from Groq: {e}")
        return "Sorry, I'm having trouble connecting to the language model. 😔 Please try again in a moment."