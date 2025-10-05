# backend/main.py

import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from document_processor import process_pdf
from vector_store import embed_chunks_and_upload_to_pinecone, query_pinecone
from llm_handler import get_chat_response
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
    
    if not app.state.current_doc_filename:
        return {"role": "bot", "content": "Please upload a document first."}

    # 1. Retrieve text context from Pinecone
    print(f"[DEBUG] Querying Pinecone...")
    text_context, matches, pages_with_images = query_pinecone(request.message)
    
    # 2. Perform Web Search (conditionally)
    web_context = None
    if request.search_web:
        print("[DEBUG] Web search enabled. Performing web search...")
        web_context = search_web(request.message)
    else:
        print("[DEBUG] Web search disabled for this query.")
    
    # 3. Handle Visual Content (VLM)
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
    
    # ==============================================================================
    # 4. Smart Context Blending
    # ==============================================================================
    MIN_DOC_CONTEXT_LENGTH = 500  # Threshold to decide if doc context is sufficient
    TOTAL_CONTEXT_LENGTH = 8000   # Max total length for combined context

    doc_ratio, web_ratio = 0.8, 0.2 # Default: 80% doc, 20% web

    if len(text_context) < MIN_DOC_CONTEXT_LENGTH and web_context:
        doc_ratio, web_ratio = 0.2, 0.8 # Flipped: 20% doc, 80% web
        print(f"[DEBUG] Not enough document context (found {len(text_context)} chars). Prioritizing web search.")
    else:
        print(f"[DEBUG] Sufficient document context found. Prioritizing document.")

    doc_limit = int(TOTAL_CONTEXT_LENGTH * doc_ratio)
    web_limit = int(TOTAL_CONTEXT_LENGTH * web_ratio)

    truncated_doc_context = text_context[:doc_limit]
    truncated_web_context = web_context[:web_limit] if web_context else ""

    # 5. Combine contexts for the final prompt
    combined_context = f"Document Context:\n{truncated_doc_context}"

    if vlm_context:
        combined_context += f"\n\nVisual Context:\n{vlm_context}"

    if truncated_web_context:
        combined_context += f"\n\nWeb Search Results:\n{truncated_web_context}"

    print(f"[DEBUG] Combined context length: {len(combined_context)}")

    # 6. Generate a final response from the LLM
    print(f"[DEBUG] Sending to LLM...")
    response_text = get_chat_response(request.message, combined_context)
    
    # 7. Gather citations
    all_pages = set([match['metadata']['page_number'] for match in matches])
    all_pages.update(vlm_pages_used)
    page_numbers = sorted(list(all_pages))

    print(f"[DEBUG] Final citations: {page_numbers}")
    print(f"{'='*80}\n")

    return {
        "role": "bot", 
        "content": response_text,
        "citations": page_numbers,
        "used_vlm": len(vlm_pages_used) > 0,
        "vlm_pages": vlm_pages_used
    }

@app.get("/")
def read_root():
    return {"message": "Hello from Veritas Backend!"}