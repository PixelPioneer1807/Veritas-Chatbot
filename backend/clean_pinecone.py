import os
from pinecone import Pinecone
from dotenv import load_dotenv

def clear_pinecone_index():
    """
    Deletes all vectors from the specified Pinecone index.
    """
    load_dotenv()

    # Get Pinecone API key from environment variables
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("Error: PINECONE_API_KEY not found in .env file.")
        return

    # Configuration
    INDEX_NAME = "veritas-hf"

    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=api_key)
        
        # Check if the index exists
        if INDEX_NAME not in pc.list_indexes().names():
            print(f"Index '{INDEX_NAME}' does not exist. Nothing to delete.")
            return

        # Get the index object
        index = pc.Index(INDEX_NAME)

        print(f"Deleting all vectors from index '{INDEX_NAME}'...")
        
        # Delete all vectors
        index.delete(delete_all=True)
        
        print(f"Successfully deleted all vectors from index '{INDEX_NAME}'.")
        
        # You can check the vector count to confirm
        stats = index.describe_index_stats()
        print(f"Current vector count: {stats['total_vector_count']}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    clear_pinecone_index()