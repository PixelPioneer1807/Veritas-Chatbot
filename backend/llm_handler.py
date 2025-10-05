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
    
    # Improved prompt engineering with better handling of visual content
    system_prompt = (
        "You are Veritas, a helpful document analysis assistant. Your task is to answer "
        "the user's question based ONLY on the provided context.\n\n"
        
        "The context may include:\n"
        "1. Text extracted directly from the document\n"
        "2. Information extracted from visual elements (charts, graphs, images) marked with '[Visual content from page X]:'\n"
        "3. Notes about the presence of visual elements\n\n"
        
        "Important instructions:\n"
        "- Answer the question directly and concisely\n"
        "- When information comes from visual content, mention that (e.g., 'According to the chart on page 3...')\n"
        "- If the answer requires information from both text and visuals, synthesize them clearly\n"
        "- If you're not confident about the answer or if the context doesn't contain the information, "
        "say 'I cannot find that information in the provided document.'\n"
        "- Do not use external knowledge or make assumptions beyond what's in the context\n"
        "- Be specific and cite page numbers when relevant\n"
    )
    
    user_prompt = f"Context:\n{context}\n\nQuestion:\n{query}"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,  # Lower temperature for more consistent, factual responses
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error getting response from Groq: {e}")
        return "Sorry, I'm having trouble connecting to the language model."