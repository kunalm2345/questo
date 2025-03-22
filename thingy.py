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
        vector_db = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
        save_faiss_to_mongo(vector_db) 
    return vector_db

# Load FAISS index (either from MongoDB or by creating a new one)
vector_db = initialize_faiss()

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

def retrieve_similar_images(query_text, top_k=2):
    """Search for similar images using FAISS."""
    query_vector = embeddings.embed_documents([query_text])[0]
    results = vector_db.similarity_search_by_vector(query_vector, k=top_k)

    for idx, result in enumerate(results, start=1):
        image_path = result.metadata.get('image_path', 'N/A')
        tags = result.metadata.get('tags', 'N/A')
        print(f"{idx}. Tags: {tags}\n🔷 Image Path: {image_path}")
        show_image(image_path)

# # ===========================
# # 🔹 10. EXAMPLE USAGE
# # ===========================
# # Add new images
# add_new_image("images/image1.png", ["math", "calculus"])
# add_new_image("images/image2.png", ["physics", "mechanics"])

# # Retrieve similar images
# retrieve_similar_images("math")
