# test_vectordb.py
from functions import load_vectordb, get_vectordb_path
import os
import faiss
import pickle
import numpy as np

def display_vectordb_contents(workspace_key):
    print(f"Examining vectordb for workspace: {workspace_key}")
    
    # Get the path to the vectordb file
    file_path = get_vectordb_path(workspace_key)
    print(f"Vectordb file path: {file_path}")
    
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"ERROR: Vectordb file does not exist at {file_path}")
        return
    
    print(f"File size: {os.path.getsize(file_path) / 1024:.2f} KB")
    
    # Load the vectordb
    try:
        vectordb = load_vectordb(workspace_key)
        print("Successfully loaded vectordb")
    except Exception as e:
        print(f"ERROR: Failed to load vectordb: {e}")
        return
    
    # Extract information from the vectordb
    try:
        # Access the FAISS index from the vectordb
        index = vectordb.index
        
        # Get the number of vectors in the index
        num_vectors = index.ntotal
        print(f"Number of vectors (entries) in the index: {num_vectors}")
        
        # Get the dimension of the vectors
        vector_dim = index.d
        print(f"Vector dimension: {vector_dim}")
        
        # Get the docstore to access metadatas
        docstore = vectordb.docstore
        
        # Print the contents
        print("\nContents of the vectordb:")
        print("-" * 80)
        print(f"{'Index':<6} {'Tag':<20} {'Image Path'}")
        print("-" * 80)
        
        # Iterate through all documents in the docstore
        count = 0
        for doc_id, doc in docstore._dict.items():
            # Skip the placeholder if it exists
            if doc.page_content == "placeholder":
                continue
            
            tag = doc.page_content
            metadata = doc.metadata
            image_path = metadata.get("image_path", "N/A")
            
            print(f"{count:<6} {tag[:20]:<20} {image_path}")
            count += 1
        
        print("-" * 80)
        print(f"Total entries (excluding placeholder): {count}")
        
        # Get unique tags and image paths
        unique_tags = set(doc.page_content for doc in docstore._dict.values() if doc.page_content != "placeholder")
        unique_images = set(doc.metadata.get("image_path", "N/A") for doc in docstore._dict.values() if doc.page_content != "placeholder")
        
        print(f"Number of unique tags: {len(unique_tags)}")
        print(f"Number of unique images: {len(unique_images)}")
        
        # Display first few unique tags
        print("\nSample of unique tags:")
        for tag in list(unique_tags)[:10]:  # Show up to 10 tags
            print(f"  - {tag}")
            
        # Display first few unique image paths
        print("\nSample of unique image paths:")
        for path in list(unique_images)[:5]:  # Show up to 5 image paths
            print(f"  - {path}")
        
    except Exception as e:
        print(f"ERROR: Failed to analyze vectordb contents: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Replace 'csf000' with your workspace key
    display_vectordb_contents("csf000")