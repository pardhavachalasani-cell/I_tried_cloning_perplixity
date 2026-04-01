import os
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import google.generativeai as genai
import rag
from werkzeug.utils import secure_filename

# Get the directory where app.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

# Configure the Gemini API
API_KEY = "AIzaSyCgOlRMcX5JbOwnLm7lQB45KHFt5uLWXSI"
genai.configure(api_key=API_KEY)

# Use gemini-2.0-flash
model = genai.GenerativeModel('gemini-2.0-flash')

# Serve frontend files (HTML, CSS, JS) from the project directory
@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/status')
def backend_status():
    return f"🚀 Backend is Alive! Model: gemini-2.0-flash. Key starts with: {API_KEY[:10]}"

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE_DIR, filename)

# Temporary directory for PDFs
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# API endpoint for PDF upload
@app.route('/api/upload', methods=['POST'])
def handle_upload():
    if 'pdf' not in request.files:
        return jsonify({"error": "No file attached"}), 400
        
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
        
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        try:
            chunks_generated = rag.process_pdf(filepath)
            return jsonify({
                "status": "success", 
                "message": f"PDF loaded and split into {chunks_generated} vector chunks.",
                "filename": filename
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "Invalid file type. Only PDF is supported."}), 400

# API endpoint to reset chat and RAG memory
@app.route('/api/reset', methods=['POST'])
def reset_memory():
    try:
        rag.PDF_KNOWLEDGE_BASE = []
        # Clear uploads folder
        for f in os.listdir(UPLOAD_FOLDER):
            os.remove(os.path.join(UPLOAD_FOLDER, f))
        return jsonify({"status": "success", "message": "Memory and files cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint for chat
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        print(f"[INFO] Received: {data}")

        if not data or not data.get('message', ''):
            return jsonify({"error": "No message provided", "status": "error"}), 400

        user_message = data['message']
        print(f"[INFO] Calling Gemini with format stream: {user_message[:50]}...")
        
        # --- RAG INJECTION LAYER ---
        # Search the PDF memory bank for chunks closely matching user question
        context = ""
        if rag.PDF_KNOWLEDGE_BASE:
            context = rag.search_query(user_message, top_k=3)
            
        # Dynamically inject context
        augmented_prompt = user_message
        if context:
            augmented_prompt = (
                f"You are a helpful AI assistant. Answer the user's question, strictly using "
                f"the following document context as your primary source of truth. If the document "
                f"does not answer the question, state so.\n\n"
                f"--- DOCUMENT CONTEXT ---\n{context}\n------------------------\n\n"
                f"QUESTION: {user_message}"
            )
            print("[INFO] Augmented prompt triggered using RAG Context.")

        # Generator function to stream chunks
        def generate():
            try:
                print(f"[DEBUG] Starting Gemini stream for: {user_message[:30]}...")
                response = model.generate_content(augmented_prompt, stream=True)
                chunk_count = 0
                for chunk in response:
                    if chunk.text:
                        chunk_count += 1
                        if chunk_count == 1:
                            print("[DEBUG] First chunk received!")
                        yield chunk.text
                
                if chunk_count == 0:
                    print("[DEBUG] Warning: Gemini returned an empty stream.")
                    yield "The AI returned an empty response. Please try rephrasing your question."
                    
            except Exception as generate_exc:
                error_str = str(generate_exc)
                print(f"[STREAM ERROR] {error_str}")
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    yield "[ERROR_429]"
                else:
                    yield f"[ERROR_GENERIC]: {error_str}"

        return Response(generate(), mimetype='text/plain')

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("  Perplexity Clone Server")
    print(f"  Serving files from: {BASE_DIR}")
    print("  Open: http://localhost:5001")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5001)
