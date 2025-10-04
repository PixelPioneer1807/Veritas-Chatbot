# backend/main.py

import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from document_processor import process_pdf
from vector_store import embed_chunks_and_upload_to_pinecone, query_pinecone
from llm_handler import get_chat_response

UPLOAD_DIRECTORY = "./uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

app = FastAPI()

origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # ... (This endpoint remains the same)
    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    chunks = process_pdf(file_path)
    if not chunks:
        return {"message": "Could not extract text from the document."}
    embed_chunks_and_upload_to_pinecone(chunks, file_id=file.filename)
    return {
        "filename": file.filename, 
        "message": f"Successfully processed '{file.filename}'. Stored {len(chunks)} chunks."
    }

@app.post("/api/chat")
def chat(request: ChatRequest):
    # --- THIS IS THE NEW RAG LOGIC ---
    # 1. Retrieve context from Pinecone
    context = query_pinecone(request.message)
    
    # 2. Generate a response from the LLM
    response_text = get_chat_response(request.message, context)
    
    return {"role": "bot", "content": response_text}

@app.get("/")
def read_root():
    return {"message": "Hello from Veritas Backend!"}