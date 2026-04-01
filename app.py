from flask import Flask, send_from_directory, request, jsonify
from google import genai
from google.genai import types
import os
import uuid

app = Flask(__name__, static_folder='.', static_url_path='')

# Initialize Google GenAI Client with the user-provided API key
API_KEY = "AIzaSyACRn_WwC2aicsiDMukfLLpSMqH2-PtntM"
client = genai.Client(api_key=API_KEY)

# In-memory conversation storage keyed by session_id
conversations = {}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/new-session', methods=['POST'])
def new_session():
    """Create a new conversation session and return its ID."""
    session_id = str(uuid.uuid4())
    conversations[session_id] = []
    return jsonify({'session_id': session_id})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('prompt', '')
    session_id = data.get('session_id', '')

    if not user_message:
        return jsonify({'error': 'No prompt provided'}), 400

    # Create a new session if one doesn't exist
    if not session_id or session_id not in conversations:
        session_id = str(uuid.uuid4())
        conversations[session_id] = []

    # Add the user's message to conversation history
    conversations[session_id].append(
        types.Content(role='user', parts=[types.Part(text=user_message)])
    )

    try:
        # Send full conversation history to Gemini for context
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=conversations[session_id],
        )

        # Add AI response to conversation history
        conversations[session_id].append(
            types.Content(role='model', parts=[types.Part(text=response.text)])
        )

        return jsonify({'text': response.text, 'session_id': session_id})
    except Exception as e:
        print(f"Error during API call: {e}")
        # Remove the failed user message from history
        conversations[session_id].pop()
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear conversation history for a session."""
    data = request.json
    session_id = data.get('session_id', '')
    if session_id in conversations:
        conversations[session_id] = []
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(port=5000, debug=True)
