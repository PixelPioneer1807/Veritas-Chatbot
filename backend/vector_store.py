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

def embed_chunks_and_upload_to_pinecone(chunks: list, file_id: str):
    # ... (This function remains the same)
    print(f"Embedding {len(chunks)} chunks for file_id: {file_id}")
    try:
        embeddings = model.encode(chunks).tolist()
        vectors_to_upsert = [
            {"id": f"{file_id}-chunk-{i}", "values": emb, "metadata": {"text": chunk}}
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


def query_pinecone(query: str, top_k: int = 3):
    """
    Embeds a query and retrieves the top_k most relevant text chunks from Pinecone.
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
    context = " ".join([match['metadata']['text'] for match in results['matches']])
    return context