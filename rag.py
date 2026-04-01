import os
import PyPDF2
import numpy as np
import google.generativeai as genai

# Configure API Key
API_KEY = "AIzaSyCgOlRMcX5JbOwnLm7lQB45KHFt5uLWXSI"
genai.configure(api_key=API_KEY)

# In-memory storage for our simplistic RAG implementation
# (Gets wiped if server restarts, which is fine for a simple app)
PDF_KNOWLEDGE_BASE = []

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def chunk_text(text, chunk_size=1000, overlap=200):
    chunks = []
    # Rudimentary overlap chunking to preserve context context boundaries
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def process_pdf(file_path):
    """ Reads PDF, breaks it into overlapping chunks, and embeds them. """
    global PDF_KNOWLEDGE_BASE
    PDF_KNOWLEDGE_BASE = [] # Reset base for new file
    
    # 1. Clean up old uploads if this is an overwrite
    text = extract_text_from_pdf(file_path)
    if not text.strip():
        raise ValueError("Could not extract any text from the PDF. It might be scanned or empty.")
        
    # 2. Chunk text
    chunks = chunk_text(text)
    
    # 3. Generate embeddings for each chunk via Google Gemini API
    # embedding-001 is the standard fast text embedding model
    print(f"[RAG] Uploaded PDF has {len(chunks)} text chunks. Generating embeddings...")
    for chunk in chunks:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=chunk,
            task_type="retrieval_document",
            title="PDF Document"
        )
        embedding = np.array(result['embedding'])
        PDF_KNOWLEDGE_BASE.append({
            "text": chunk,
            "embedding": embedding
        })
        
    print(f"[RAG] Successfully processed {len(PDF_KNOWLEDGE_BASE)} chunks into vector memory.")
    return len(PDF_KNOWLEDGE_BASE)

def cosine_similarity(a, b):
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot_product / (norm_a * norm_b)

def search_query(query_text, top_k=3):
    """ Takes a user question, searches PDF chunks, and returns most relevant text. """
    if not PDF_KNOWLEDGE_BASE:
        return "" # No PDF loaded
        
    # 1. Embed the user's question
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=query_text,
        task_type="retrieval_query",
    )
    query_embedding = np.array(result['embedding'])
    
    # 2. Score similarity of query vs all PDF chunks
    scored_chunks = []
    for item in PDF_KNOWLEDGE_BASE:
        score = cosine_similarity(query_embedding, item['embedding'])
        scored_chunks.append((score, item['text']))
        
    # 3. Sort by score descending (highest match first)
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # 4. Extract top K blocks of text
    top_chunks = scored_chunks[:top_k]
    
    # Combine the texts with a divider
    context = "\n\n...[jump to next section]...\n\n".join([chunk[1] for chunk in top_chunks])
    print(f"[RAG] Found matching context bounds with max confidence: {top_chunks[0][0]:.3f}")
    return context
