# backend/main.py

import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from document_processor import process_pdf
from vector_store import embed_chunks_and_upload_to_pinecone, query_pinecone
from llm_handler import get_chat_response, is_casual_conversation
from vlm_handler import query_image_with_vlm, is_visual_query, analyze_chart_comprehensively
from web_search import search_web

UPLOAD_DIRECTORY = "./uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

app = FastAPI()

origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.state.current_doc_filename = None

class ChatRequest(BaseModel):
    message: str
    search_web: bool = True

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    app.state.current_doc_filename = file.filename
        
    chunks_with_metadata = process_pdf(file_path)
    if not chunks_with_metadata:
        return {"message": "Could not extract text from the document."}
        
    embed_chunks_and_upload_to_pinecone(chunks_with_metadata, file_id=file.filename)
    
    return {
        "filename": file.filename,
        "message": f"Successfully processed '{file.filename}'. Stored {len(chunks_with_metadata)} chunks."
    }

def get_image_path_from_page(page_number):
    """Constructs the path to the saved page image."""
    page_num_int = int(page_number)
    
    image_dir = os.path.join(UPLOAD_DIRECTORY, "images")
    image_path = os.path.join(image_dir, f"page_{page_num_int}.png")
    
    print(f"[DEBUG] Looking for image at: {image_path}")
    print(f"[DEBUG] Image exists: {os.path.exists(image_path)}")
    
    if os.path.exists(image_path):
        return image_path
    return None


@app.post("/api/chat")
def chat(request: ChatRequest):
    print(f"\n{'='*80}")
    print(f"[DEBUG] New Query: {request.message}")
    print(f"[DEBUG] Web Search Enabled: {request.search_web}")
    print(f"{'='*80}")
    
    # Check for casual conversation first (no document needed)
    is_casual, casual_response = is_casual_conversation(request.message)
    if is_casual:
        print("[DEBUG] Casual conversation detected - responding directly")
        return {
            "role": "bot",
            "content": casual_response,
            "citations": [],
            "used_vlm": False,
            "vlm_pages": [],
            "rag_response": casual_response,
            "web_response": None,
            "response_type": "casual"
        }
    
    if not app.state.current_doc_filename:
        return {
            "role": "bot",
            "content": "Please upload a document first.",
            "citations": [],
            "used_vlm": False,
            "vlm_pages": [],
            "rag_response": None,
            "web_response": None,
            "response_type": "no_document"
        }

    # 1. Retrieve text context from Pinecone (RAG)
    print(f"[DEBUG] Querying Pinecone...")
    text_context, matches, pages_with_images = query_pinecone(request.message)
    
    # 2. Handle Visual Content (VLM)
    vlm_context = ""
    vlm_pages_used = []
    query_is_visual = is_visual_query(request.message)
    print(f"[DEBUG] Is visual query: {query_is_visual}")
    
    if query_is_visual and pages_with_images:
        print(f"[DEBUG] ✓ Visual query detected with image pages!")
        print(f"[DEBUG] Pages with images in results: {list(pages_with_images.keys())}")
        
        sorted_pages = sorted(pages_with_images.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"[DEBUG] Processing top pages: {[p[0] for p in sorted_pages]}")
        
        for page_num, score in sorted_pages:
            image_path = get_image_path_from_page(page_num)
            if image_path:
                print(f"[DEBUG] → Querying VLM for page {page_num} (score: {score:.3f})")
                
                if any(word in request.message.lower() for word in ['chart', 'graph', 'value', 'rating', 'score', 'barrier', 'number', 'scale', 'issue']):
                    print(f"[DEBUG] → Using comprehensive chart analysis")
                    vlm_answer = analyze_chart_comprehensively(image_path, request.message)
                else:
                    print(f"[DEBUG] → Using standard VLM query")
                    vlm_answer = query_image_with_vlm(image_path, request.message)
                
                if vlm_answer and len(vlm_answer) > 10 and "Could not extract" not in vlm_answer and "Error" not in vlm_answer:
                    vlm_context += f"\n\n[Visual content from page {page_num}]: {vlm_answer}"
                    vlm_pages_used.append(page_num)
    
    # 3. Build RAG context (Document + Visual)
    rag_context = f"Document Context:\n{text_context}"
    if vlm_context:
        rag_context += f"\n\nVisual Context:\n{vlm_context}"
    
    print(f"[DEBUG] RAG context length: {len(rag_context)}")
    
    # 4. Generate RAG-only response
    print(f"[DEBUG] Generating RAG response...")
    rag_response = get_chat_response(request.message, rag_context)
    
    # 5. Perform Web Search and generate web-enhanced response (if enabled)
    web_response = None
    web_sources = []
    if request.search_web:
        print("[DEBUG] Web search enabled. Performing web search...")
        web_search_results = search_web(request.message)
        
        if web_search_results:
            # Extract web sources for citation
            web_sources = extract_web_sources(web_search_results)
            
            # Generate web-enhanced response
            combined_context = rag_context + f"\n\nWeb Search Results:\n{web_search_results}"
            print(f"[DEBUG] Combined context length: {len(combined_context)}")
            print(f"[DEBUG] Generating web-enhanced response...")
            web_response = get_chat_response(request.message, combined_context)
        else:
            print("[DEBUG] No web search results found")
    else:
        print("[DEBUG] Web search disabled for this query.")
    
    # 6. Gather citations from document
    all_pages = set([match['metadata']['page_number'] for match in matches])
    all_pages.update(vlm_pages_used)
    page_numbers = sorted(list(all_pages))

    print(f"[DEBUG] Document citations: {page_numbers}")
    print(f"[DEBUG] Web sources: {len(web_sources)}")
    print(f"{'='*80}\n")

    return {
        "role": "bot",
        "content": web_response if web_response else rag_response,  # Primary response
        "rag_response": rag_response,  # RAG-only response
        "web_response": web_response,  # Web-enhanced response
        "web_sources": web_sources,  # List of web sources
        "citations": page_numbers,  # Document page citations
        "used_vlm": len(vlm_pages_used) > 0,
        "vlm_pages": vlm_pages_used,
        "response_type": "document_query"
    }

def extract_web_sources(web_results: str) -> list:
    """Extract source titles and links from web search results."""
    sources = []
    if not web_results:
        return sources
    
    # Split by separator
    results = web_results.split("\n\n---\n\n")
    
    for result in results:
        lines = result.strip().split("\n")
        title = None
        link = None
        
        for line in lines:
            if line.startswith("Title: "):
                title = line.replace("Title: ", "").strip()
            elif line.startswith("Link: "):
                link = line.replace("Link: ", "").strip()
        
        if title and link and link != "N/A":
            sources.append({"title": title, "link": link})
    
    return sources[:5]  # Return top 5 sources

@app.get("/")
def read_root():
    return {"message": "Hello from Veritas Backend!"}