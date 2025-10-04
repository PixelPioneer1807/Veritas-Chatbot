# backend/document_processor.py

from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def process_pdf(file_path: str):
    """
    Extracts text from a PDF and splits it into chunks.
    """
    print(f"Processing file: {file_path}")
    
    # 1. Extract text from PDF
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    
    if not text:
        print("Could not extract text from PDF.")
        return []

    # 2. Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text=text)
    
    print(f"Successfully split text into {len(chunks)} chunks.")
    return chunks