# backend/llm_handler.py

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

def get_chat_response(query: str, context: str):
    """
    Generates a response from the LLM based on the user's query and retrieved context.
    """
    
    # This is our prompt engineering. We instruct the LLM on how to behave.
    system_prompt = (
        "You are a helpful assistant named Veritas. Your task is to answer the user's question "
        "based ONLY on the provided context. Do not use any external knowledge. "
        "If the answer is not available in the context, say 'I cannot answer that question based "
        "on the provided document.'"
    )
    
    user_prompt = f"Context:\n{context}\n\nQuestion:\n{query}"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile", # Or another model like "mixtral-8x7b-32768"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error getting response from Groq: {e}")
        return "Sorry, I'm having trouble connecting to the language model."