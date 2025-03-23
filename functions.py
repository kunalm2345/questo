# functions.py
from langchain_community.vectorstores.faiss import FAISS
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
import uuid
import pickle
import os
import io

# Initialize the embeddings model
def get_embeddings():
    print("1. Starting to initialize the embeddings model")
    embeddings = HuggingFaceEmbeddings(model_name="thenlper/gte-large")
    print("2. Embeddings model initialized successfully")
    return embeddings

# Ensure the vectordb directory exists
def ensure_vectordb_dir(workspace_id):
    print(f"3. Ensuring vectordb directory exists for workspace {workspace_id}")
    # Create base vectordb directory if it doesn't exist
    base_dir = os.path.join("static", "vectordb")
    if not os.path.exists(base_dir):
        print("4. Creating base vectordb directory")
        os.makedirs(base_dir)
    else:
        print("4. Base vectordb directory already exists")
    
    # Create workspace-specific directory if it doesn't exist
    workspace_dir = os.path.join(base_dir, f"workspace_{workspace_id}")
    if not os.path.exists(workspace_dir):
        print(f"5. Creating workspace-specific directory for {workspace_id}")
        os.makedirs(workspace_dir)
    else:
        print(f"5. Workspace-specific directory for {workspace_id} already exists")
    
    print(f"6. Directory path: {workspace_dir}")
    return workspace_dir

# Get the path to the vectordb file for a workspace
def get_vectordb_path(workspace_id):
    print(f"7. Getting vectordb file path for workspace {workspace_id}")
    workspace_dir = ensure_vectordb_dir(workspace_id)
    file_path = os.path.join(workspace_dir, "vectordb.pkl")
    print(f"8. Vectordb file path: {file_path}")
    return file_path

# Save a vectordb to disk
def save_vectordb(vectordb, workspace_id):
    print(f"9. Saving vectordb for workspace {workspace_id}")
    file_path = get_vectordb_path(workspace_id)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    print("10. Directory confirmed to exist")
    
    try:
        # Save the vectordb to disk
        with open(file_path, 'wb') as f:
            pickle.dump(vectordb, f)
        print(f"11. Vectordb saved successfully to {file_path}")
        return True
    except Exception as e:
        print(f"11. ERROR: Failed to save vectordb: {e}")
        return False

# Load a vectordb from disk
def load_vectordb(workspace_id):
    print(f"12. Loading vectordb for workspace {workspace_id}")
    file_path = get_vectordb_path(workspace_id)
    
    if os.path.exists(file_path):
        print(f"13. Vectordb file exists at {file_path}")
        try:
            with open(file_path, 'rb') as f:
                vectordb = pickle.load(f)
            print("14. Vectordb loaded successfully")
            return vectordb
        except Exception as e:
            print(f"14. ERROR: Failed to load vectordb: {e}")
    else:
        print(f"13. Vectordb file does not exist at {file_path}")
    
    # If file doesn't exist or loading failed, create a new one
    print("15. Creating new vectordb")
    return create_vectordb(workspace_id)

# Create a new vectordb for a workspace
def create_vectordb(workspace_id):
    print(f"16. Creating new vectordb for workspace {workspace_id}")
    # Initialize embeddings
    embeddings = get_embeddings()
    print("17. Got embeddings for new vectordb")
    
    # Create an empty FAISS index
    print("18. Creating empty FAISS index")
    vectordb = FAISS.from_texts(texts=["placeholder"], embedding=embeddings)
    print("19. Empty FAISS index created")
    
    # Save to disk
    success = save_vectordb(vectordb, workspace_id)
    if success:
        print("20. New vectordb saved successfully")
    else:
        print("20. WARNING: Failed to save new vectordb")
    
    return vectordb

# Add a new entry to the vectordb
def add_to_vectordb(workspace_id, tag, image_path):
    print(f"21. Adding entry to vectordb for workspace {workspace_id}")
    print(f"22. Tag: {tag}, Image path: {image_path}")
    
    # Load the existing vectordb
    vectordb = load_vectordb(workspace_id)
    print("23. Loaded existing vectordb (or created new one)")
    
    # Add the new entry
    try:
        print("24. Adding new entry to vectordb")
        vectordb.add_texts(
            texts=[tag],
            metadatas=[{"tag": tag, "image_path": image_path}],
            ids=[str(uuid.uuid4())]
        )
        print("25. Entry added successfully")
    except Exception as e:
        print(f"25. ERROR: Failed to add entry: {e}")
        raise e
    
    # Save the updated vectordb
    success = save_vectordb(vectordb, workspace_id)
    if success:
        print("26. Updated vectordb saved successfully")
    else:
        print("26. WARNING: Failed to save updated vectordb")
    
    return vectordb

# Check if a vectordb exists for a workspace
def vectordb_exists(workspace_id):
    print(f"27. Checking if vectordb exists for workspace {workspace_id}")
    file_path = get_vectordb_path(workspace_id)
    exists = os.path.exists(file_path)
    print(f"28. Vectordb exists: {exists}")
    return exists

# functions.py (add this function)

def search_vectordb(workspace_id, query_text, top_k=3):
    """
    Search the vectordb for a given query and return the top_k most similar entries
    """
    print(f"Searching vectordb for workspace {workspace_id} with query: {query_text}")
    
    # Load the vectordb
    vectordb = load_vectordb(workspace_id)
    
    # Get embeddings for the query
    embeddings = get_embeddings()
    query_embedding = embeddings.embed_query(query_text)
    
    try:
        # Search the vectordb using the query
        results = vectordb.similarity_search_with_score(query_text, k=top_k)
        print(f"Found {len(results)} results with scores")
        
        # Extract and return the results
        search_results = []
        for doc, score in results:
            # Skip placeholder entries
            if doc.page_content == "placeholder":
                continue
                
            search_results.append({
                "tag": doc.page_content,
                "image_path": doc.metadata.get("image_path", ""),
                "score": float(score)  # Convert to float for better display
            })
            
        print(f"Returning {len(search_results)} filtered search results")
        return search_results
    
    except Exception as e:
        print(f"Error during vectordb search: {e}")
        # Fallback to regular similarity search
        try:
            results = vectordb.similarity_search(query_text, k=top_k)
            
            search_results = []
            for doc in results:
                # Skip placeholder entries
                if doc.page_content == "placeholder":
                    continue
                    
                search_results.append({
                    "tag": doc.page_content,
                    "image_path": doc.metadata.get("image_path", ""),
                    "score": None  # No score available
                })
            
            return search_results
        except Exception as e:
            print(f"Fallback search also failed: {e}")
            return []