import fitz  # PyMuPDF
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter

def process_pdf(file_path: str):
    """
    Extracts text from each page. If a page contains images, it saves a
    snapshot of the entire page and marks chunks as having visual content.
    """
    print(f"Processing file: {file_path}")
    
    image_dir = os.path.join(os.path.dirname(file_path), "images")
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    doc = fitz.open(file_path)
    chunks_with_metadata = []
    
    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        has_images = False
        
        # Check if the page has any images
        if page.get_images(full=True):
            has_images = True
            # Render the entire page as a high-quality image (pixmap)
            pix = page.get_pixmap(dpi=300)
            image_filename = f"page_{page_num + 1}.png"
            image_path = os.path.join(image_dir, image_filename)
            pix.save(image_path)
            
            # DON'T add generic image reference text that pollutes embeddings
            # Instead, we'll use metadata to track this

        # Skip chunking if page is mostly empty
        if len(page_text.strip()) < 50 and not has_images:
            continue

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        chunks = text_splitter.split_text(text=page_text)
        
        # If no text but has images, create a minimal chunk
        if not chunks and has_images:
            chunks = [f"Page {page_num + 1} contains visual content."]
        
        for chunk in chunks:
            chunks_with_metadata.append({
                'text': chunk,
                'page_number': page_num + 1,
                'has_images': has_images  # Track this in metadata
            })

    if not chunks_with_metadata:
        print("Could not extract text from PDF.")
        return []

    print(f"Successfully processed and split file into {len(chunks_with_metadata)} chunks.")
    return chunks_with_metadata