# backend/main.py (DEBUG VERSION)

import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from document_processor import process_pdf
from vector_store import embed_chunks_and_upload_to_pinecone, query_pinecone
from llm_handler import get_chat_response
from vlm_handler import query_image_with_vlm, is_visual_query, analyze_chart_comprehensively

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
    # Convert to int in case it's a float from Pinecone
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
    print(f"{'='*80}")
    
    if not app.state.current_doc_filename:
        return {"role": "bot", "content": "Please upload a document first."}

    # 1. Retrieve text context from Pinecone
    print(f"[DEBUG] Querying Pinecone...")
    text_context, matches, pages_with_images = query_pinecone(request.message)
    
    print(f"[DEBUG] Retrieved {len(matches)} matches")
    print(f"[DEBUG] Pages with images found: {pages_with_images}")
    
    # 2. Determine if this is a visual query
    query_is_visual = is_visual_query(request.message)
    print(f"[DEBUG] Is visual query: {query_is_visual}")
    
    # 3. Query VLM only if:
    #    a) The query is about visual content, AND
    #    b) Retrieved chunks include pages with images
    vlm_context = ""
    vlm_pages_used = []
    
    if query_is_visual and pages_with_images:
        print(f"[DEBUG] ✓ Visual query detected with image pages!")
        print(f"[DEBUG] Pages with images in results: {list(pages_with_images.keys())}")
        
        # Sort pages by relevance score and process top 3 at most
        sorted_pages = sorted(pages_with_images.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"[DEBUG] Processing top pages: {[p[0] for p in sorted_pages]}")
        
        for page_num, score in sorted_pages:
            image_path = get_image_path_from_page(page_num)
            if image_path:
                print(f"[DEBUG] → Querying VLM for page {page_num} (score: {score:.3f})")
                
                # For chart/data queries, use comprehensive analysis
                if any(word in request.message.lower() for word in ['chart', 'graph', 'value', 'rating', 'score', 'barrier', 'number', 'scale', 'issue']):
                    print(f"[DEBUG] → Using comprehensive chart analysis")
                    vlm_answer = analyze_chart_comprehensively(image_path, request.message)
                else:
                    print(f"[DEBUG] → Using standard VLM query")
                    vlm_answer = query_image_with_vlm(image_path, request.message)
                
                print(f"[DEBUG] → VLM raw answer length: {len(vlm_answer)}")
                print(f"[DEBUG] → VLM answer preview: {vlm_answer[:200]}...")
                
                # Only include VLM output if it's substantive
                if vlm_answer and len(vlm_answer) > 10 and "Could not extract" not in vlm_answer and "Error" not in vlm_answer:
                    vlm_context += f"\n\n[Visual content from page {page_num}]: {vlm_answer}"
                    vlm_pages_used.append(page_num)
                    print(f"[DEBUG] ✓ VLM answer added to context")
                else:
                    print(f"[DEBUG] ✗ VLM answer rejected: {vlm_answer[:100]}")
            else:
                print(f"[DEBUG] ✗ Image path not found for page {page_num}")
    
    elif pages_with_images and not query_is_visual:
        print(f"[DEBUG] Query is NOT visual, but pages with images were retrieved: {list(pages_with_images.keys())}")
        # Add a brief note that visual content exists but wasn't analyzed
        pages_list = ', '.join(map(str, sorted(pages_with_images.keys())))
        vlm_context = f"\n\n[Note: Pages {pages_list} contain visual elements like charts or images, but were not analyzed as the query doesn't appear to be about visual content.]"
    
    else:
        if not query_is_visual:
            print(f"[DEBUG] Not a visual query")
        if not pages_with_images:
            print(f"[DEBUG] No pages with images in results")

    # 4. Combine contexts intelligently
    if vlm_context:
        combined_context = f"{text_context}\n{vlm_context}"
        print(f"[DEBUG] Combined context length: {len(combined_context)}")
        print(f"[DEBUG] VLM context added: YES")
    else:
        combined_context = text_context
        print(f"[DEBUG] VLM context added: NO")

    # 5. Generate a final response from the LLM
    print(f"[DEBUG] Sending to LLM...")
    response_text = get_chat_response(request.message, combined_context)
    print(f"[DEBUG] LLM response length: {len(response_text)}")
    
    # 6. Gather all relevant page numbers
    all_pages = set([match['metadata']['page_number'] for match in matches])
    all_pages.update(vlm_pages_used)
    page_numbers = sorted(list(all_pages))

    print(f"[DEBUG] Final citations: {page_numbers}")
    print(f"[DEBUG] VLM was used: {len(vlm_pages_used) > 0}")
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