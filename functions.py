import os
import uuid
import pickle
import gridfs
from pymongo import MongoClient
from langchain_community.vectorstores.faiss import FAISS
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from PIL import Image

# CONNECT TO MONGODB
client = MongoClient("mongodb+srv://f20231146:Zc2Li5sO9UG6ZeEo@cluster0.koj5w.mongodb.net/?retryWrites=true&w=majority")
db = client['questoDB'] 
collection = db["image_metadata"]  
fs = gridfs.GridFS(db)  

embeddings = HuggingFaceEmbeddings(model_name="thenlper/gte-large")

# Path to FAISS index (if saved locally)
# index_path = "faiss_index"

# SAVE IMAGE METADATA IN MONGODB
def save_image_metadata(file_path, tags):
    """Save image metadata (file path & tags) in MongoDB."""
    image_entry = {"file_path": file_path, "tags": tags}
    collection.insert_one(image_entry)
    print(f"✅ Image metadata saved: {file_path}")

# 4. LOAD FAISS INDEX FROM MONGODB
def load_faiss_from_mongo():
    """Load FAISS index from MongoDB and deserialize it."""
    faiss_file = fs.find_one({"filename": "faiss_index"})
    if faiss_file:
        faiss_bytes = faiss_file.read()  
        vector_db = pickle.loads(faiss_bytes) 
        print("✅ FAISS index loaded from MongoDB.")
        return vector_db
    else:
        print("⚠️ No FAISS index found in MongoDB. Creating a new one.")
        return None

# SAVE FAISS INDEX TO MONGODB
def save_faiss_to_mongo(vector_db):
    """Convert FAISS index to binary and save in MongoDB."""
    faiss_bytes = pickle.dumps(vector_db) 
    old_index = fs.find_one({"filename": "faiss_index"})  
    if old_index:
        fs.delete(old_index._id)  
    fs.put(faiss_bytes, filename="faiss_index")  
    print("✅ FAISS index saved in MongoDB.")

# LOAD METADATA & INITIALIZE FAISS
def load_existing_metadata():
    """Load image metadata from MongoDB."""
    images = collection.find({})
    texts = [" ".join(img["tags"]) for img in images]  
    metadatas = [{"image_path": img["file_path"], "tags": img["tags"]} for img in images]
    return texts, metadatas

def initialize_faiss():
    """Load FAISS from MongoDB or create a new one."""
    vector_db = load_faiss_from_mongo()
    
    if vector_db is None:
        texts, metadatas = load_existing_metadata()
        
        # If there's no existing data, create a dummy entry to initialize FAISS
        if not texts:
            print("No existing data found. Creating a dummy entry to initialize FAISS.")
            texts = ["dummy entry"]
            metadatas = [{"image_path": "dummy_path", "tags": ["dummy"]}]
        
        vector_db = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
        save_faiss_to_mongo(vector_db) 
    return vector_db

# Load FAISS index (either from MongoDB or by creating a new one)
# vector_db = initialize_faiss()
vector_db = None

# UPDATE FAISS INDEX & SAVE TO MONGODB
def update_faiss_and_save(file_path, tags):
    """Update FAISS index and save the new version in MongoDB."""
    text_representation = " ".join(tags)
    metadata = {"image_path": file_path, "tags": tags}
    
    # Add new data to FAISS
    vector_db.add_texts([text_representation], metadatas=[metadata], ids=[str(uuid.uuid4())])
    
    # Save updated FAISS index to MongoDB
    save_faiss_to_mongo(vector_db)
    print(f"✅ FAISS index updated with {file_path}.")


# ADD NEW IMAGE
def add_new_image(file_path, tags):
    """Save image metadata and update FAISS index."""
    save_image_metadata(file_path, tags)  
    update_faiss_and_save(file_path, tags)  

# 9. RETRIEVE SIMILAR IMAGES
def show_image(image_path):
    """Display an image."""
    img = Image.open(image_path)
    img.show()

def retrieve_similar_images(query_text, question_ids, top_k=5):
    """
    Search for similar questions using FAISS or fallback to text search.
    
    Parameters:
    query_text (str): The search query
    question_ids (list): List of question IDs to filter the results
    top_k (int): Maximum number of results to return
    
    Returns:
    list: List of question IDs that match the search query
    """
    global vector_db
    
    # Initialize vector_db if not already done
    if vector_db is None:
        try:
            vector_db = initialize_faiss()
        except Exception as e:
            print(f"Error initializing FAISS: {e}")
            # If FAISS initialization fails, fall back to text search
            return fallback_text_search(query_text, question_ids, top_k)
    
    try:
        # Attempt FAISS search
        query_vector = embeddings.embed_documents([query_text])[0]
        
        # Use the vector_db to search
        results = vector_db.similarity_search_by_vector(query_vector, k=top_k * 3)
        
        # Extract matching IDs
        matched_ids = []
        for result in results:
            image_path = result.metadata.get('image_path', '')
            
            # Check if this corresponds to any of our question IDs
            for question_id in question_ids:
                if question_id in image_path:
                    matched_ids.append(question_id)
                    break
        
        # If no matches found with FAISS, fall back to text search
        if not matched_ids:
            print("No FAISS matches found, falling back to text search")
            return fallback_text_search(query_text, question_ids, top_k)
        
        return matched_ids[:top_k]
        
    except Exception as e:
        print(f"Error in FAISS search: {e}")
        # Fall back to text search on any error
        return fallback_text_search(query_text, question_ids, top_k)

def fallback_text_search(query_text, question_ids, top_k=5):
    """
    Fallback text search when FAISS fails or returns no results.
    """
    print("Using fallback text search")
    
    # Handle empty question_ids
    if not question_ids:
        return []
    
    try:
        # Convert string IDs to ObjectId for MongoDB query
        object_ids = [ObjectId(qid) for qid in question_ids]
        
        # Fetch all questions with the given IDs
        questions = list(q_coll.find({"_id": {"$in": object_ids}}))
        
        # Simple matching: Look for any questions containing the query terms
        query_terms = [term.lower() for term in query_text.split()]
        matching_questions = []
        
        for question in questions:
            # Check if any query term is in the question text or tags
            question_text = question.get("ques_txt", "").lower()
            question_tags = [tag.lower() for tag in question.get("tags", [])]
            
            # Count how many terms match
            match_count = 0
            for term in query_terms:
                if term in question_text or any(term in tag for tag in question_tags):
                    match_count += 1
            
            # If any matches, add to our list with a match score
            if match_count > 0:
                matching_questions.append((str(question["_id"]), match_count))
        
        # Sort by match count (descending) and return top_k IDs
        matching_questions.sort(key=lambda x: x[1], reverse=True)
        matching_ids = [q[0] for q in matching_questions[:top_k]]
        
        return matching_ids
    except Exception as e:
        print(f"Error in fallback text search: {e}")
        # If everything fails, return some random IDs as a last resort
        return question_ids[:min(top_k, len(question_ids))]

# # ===========================
# # 🔹 10. EXAMPLE USAGE
# # ===========================
# # Add new images
# add_new_image("images/image1.png", ["math", "calculus"])
# add_new_image("images/image2.png", ["physics", "mechanics"])

# # Retrieve similar images
# retrieve_similar_images("math")
