import os
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()
print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Embedding model loaded.")

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
INDEX_NAME = "veritas-hf"
index = pc.Index(INDEX_NAME)

def embed_chunks_and_upload_to_pinecone(chunks_with_metadata: list, file_id: str):
    """
    Embeds chunks and uploads them to Pinecone with metadata.
    """
    print(f"Embedding {len(chunks_with_metadata)} chunks for file_id: {file_id}")
    try:
        # Separate the chunks from the metadata
        chunks = [item['text'] for item in chunks_with_metadata]
        
        embeddings = model.encode(chunks).tolist()
        
        vectors_to_upsert = [
            {
                "id": f"{file_id}-chunk-{i}",
                "values": emb,
                "metadata": {
                    "text": chunk,
                    "page_number": chunks_with_metadata[i]['page_number'],
                    "has_images": chunks_with_metadata[i].get('has_images', False),  # Store image flag
                    "file_id": file_id
                }
            }
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
        
        if not vectors_to_upsert:
            print("No vectors to upsert.")
            return
            
        print(f"Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
        index.upsert(vectors=vectors_to_upsert)
        print("Successfully upserted vectors to Pinecone.")
        
    except Exception as e:
        print(f"An error occurred during embedding or upserting: {e}")


def query_pinecone(query: str, top_k: int = 6):
    """
    Embeds a query and retrieves the top_k most relevant text chunks from Pinecone.
    Returns context, matches, and pages with images separately.
    """
    # Embed the query
    query_embedding = model.encode(query).tolist()
    
    # Query Pinecone
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    
    # Extract the text from the metadata
    matches = results['matches']
    context = " ".join([match['metadata']['text'] for match in matches])
    
    # Identify pages with images from the retrieved chunks
    pages_with_images = {}
    for match in matches:
        if match['metadata'].get('has_images', False):
            page_num = match['metadata']['page_number']
            score = match['score']
            # Keep track of relevance score for each page
            if page_num not in pages_with_images or score > pages_with_images[page_num]:
                pages_with_images[page_num] = score
    
    return context, matches, pages_with_images