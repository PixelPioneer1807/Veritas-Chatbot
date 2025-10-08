# backend/main.py

import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio

from document_processor import process_pdf
from vector_store import embed_chunks_and_upload_to_pinecone, query_pinecone
from llm_handler import get_chat_response, is_casual_conversation
from vlm_handler import query_image_with_vlm, is_visual_query, analyze_chart_comprehensively
from web_search import search_web
import database

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
app.state.chat_history = []

class ChatRequest(BaseModel):
    message: str
    search_web: bool = True

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Add document to the database
    db_document = database.Document(filename=file.filename)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    app.state.current_doc_filename = file.filename
    app.state.chat_history = []  # Reset chat history on new upload

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
async def chat(request: ChatRequest):
    print(f"\n{'='*80}")
    print(f"[DEBUG] New Query: {request.message}")
    print(f"[DEBUG] Web Search Enabled: {request.search_web}")
    print(f"{'='*80}")

    app.state.chat_history.append({"role": "user", "content": request.message})

    is_casual, casual_response = is_casual_conversation(request.message)
    if is_casual:
        print("[DEBUG] Casual conversation detected - responding directly")
        app.state.chat_history.append({"role": "assistant", "content": casual_response})
        
        # Send metadata first, then stream the response
        async def casual_stream():
            metadata = {
                "type": "metadata",
                "citations": [],
                "used_vlm": False,
                "vlm_pages": [],
                "response_type": "casual"
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': casual_response})}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(casual_stream(), media_type="text/event-stream")

    if not app.state.current_doc_filename:
        no_doc_response = "Please upload a document first."
        app.state.chat_history.append({"role": "bot", "content": no_doc_response})
        
        async def no_doc_stream():
            metadata = {
                "type": "metadata",
                "citations": [],
                "used_vlm": False,
                "vlm_pages": [],
                "response_type": "no_document"
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': no_doc_response})}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(no_doc_stream(), media_type="text/event-stream")

    print(f"[DEBUG] Querying Pinecone...")
    text_context, matches, pages_with_images = query_pinecone(request.message)

    if not matches or matches[0]['score'] < 0.2:
        print("[DEBUG] Low relevance to document. Using general LLM.")
        
        async def general_stream():
            metadata = {
                "type": "metadata",
                "citations": [],
                "used_vlm": False,
                "vlm_pages": [],
                "response_type": "general"
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            full_response = ""
            async for chunk in get_chat_response(request.message, "No relevant document context found.", app.state.chat_history, stream=True):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            app.state.chat_history.append({"role": "bot", "content": full_response})
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(general_stream(), media_type="text/event-stream")

    # Extract citation pages from matches
    citation_pages = []
    for match in matches:
        page_num = match['metadata'].get('page_number')
        if page_num and page_num not in citation_pages:
            citation_pages.append(page_num)
    
    citation_pages = sorted(citation_pages)[:5]  # Top 5 pages
    print(f"[DEBUG] Citation pages: {citation_pages}")

    async def response_generator():
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

        rag_context = f"Document Context:\n{text_context}"
        if vlm_context:
            rag_context += f"\n\nVisual Context:\n{vlm_context}"

        print(f"[DEBUG] RAG context length: {len(rag_context)}")

        # Send metadata first
        metadata = {
            "type": "metadata",
            "citations": citation_pages,
            "used_vlm": bool(vlm_pages_used),
            "vlm_pages": vlm_pages_used,
            "response_type": "document_query"
        }
        yield f"data: {json.dumps(metadata)}\n\n"

        full_response = ""
        if request.search_web:
            print("[DEBUG] Web search enabled. Performing web search...")
            web_search_results = search_web(request.message)

            if web_search_results:
                combined_context = rag_context + f"\n\nWeb Search Results:\n{web_search_results}"
                print(f"[DEBUG] Combined context length: {len(combined_context)}")
                print(f"[DEBUG] Generating web-enhanced response...")
                async for chunk in get_chat_response(request.message, combined_context, app.state.chat_history, stream=True):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            else:
                print("[DEBUG] No web search results found")
                async for chunk in get_chat_response(request.message, rag_context, app.state.chat_history, stream=True):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        else:
            print("[DEBUG] Web search disabled for this query.")
            async for chunk in get_chat_response(request.message, rag_context, app.state.chat_history, stream=True):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        app.state.chat_history.append({"role": "bot", "content": full_response})
        yield "data: [DONE]\n\n"

    return StreamingResponse(response_generator(), media_type="text/event-stream")

def extract_web_sources(web_results: str) -> list:
    """Extract source titles and links from web search results."""
    sources = []
    if not web_results:
        return sources

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

    return sources[:5]

@app.get("/")
def read_root():
    return {"message": "Hello from Veritas Backend!"}