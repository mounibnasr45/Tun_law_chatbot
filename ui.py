import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import json
import uuid
from enum import Enum

# Configuration
API_URL = "http://localhost:8000"  # Update if your API is hosted elsewhere
LEGAL_FIELDS = ["criminal", "constitution"]
LANGUAGES = ["fr", "en"]

# Enums for feedback
class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTION = "correction"

# Initialize session state
def initialize_session_state():
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "current_query_id" not in st.session_state:
        st.session_state.current_query_id = None
    if "feedback_given" not in st.session_state:
        st.session_state.feedback_given = {}
    if "model_settings" not in st.session_state:
        st.session_state.model_settings = {
            "temperature": 0.7,
            "max_tokens": 150,
            "top_k": 3,
            "enable_reflection": True
        }
    if "last_response" not in st.session_state:
        st.session_state.last_response = None

initialize_session_state()

# Helper functions
def send_query(query, field, language="fr"):
    """Send query to the API with current settings"""
    payload = {
        "query": query,
        "field": field,
        "language": language,
        "top_k": st.session_state.model_settings["top_k"],
        "max_tokens": st.session_state.model_settings["max_tokens"],
        "temperature": st.session_state.model_settings["temperature"],
        "enable_reflection": st.session_state.model_settings["enable_reflection"]
    }
    
    try:
        response = requests.post(f"{API_URL}/query", json=payload)
        if response.status_code == 200:
            data = response.json()
            st.session_state.current_query_id = data.get("query_id")
            st.session_state.last_response = data
            return data
        else:
            st.error(f"API Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None

def submit_feedback(feedback_type, correction_text=None, comments=None):
    """Submit feedback to the API"""
    if not st.session_state.get('last_response') or not st.session_state.last_response.get('query_id'):
        st.warning("No active query to provide feedback on")
        return False
    
    payload = {
        "query_id": st.session_state.last_response['query_id'],
        "feedback_type": feedback_type.value if isinstance(feedback_type, Enum) else feedback_type,
        "correction_text": correction_text,
        "comments": comments
    }
    
    try:
        response = requests.post(f"{API_URL}/feedback", json=payload)
        if response.status_code == 201:
            st.session_state.feedback_given[st.session_state.last_response['query_id']] = feedback_type
            st.success("Feedback submitted successfully!")
            return True
        else:
            st.error(f"Feedback Error: {response.text}")
            return False
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return False

def get_reflection():
    """Get self-reflection from the API"""
    if not st.session_state.get('last_response') or not st.session_state.last_response.get('query_id'):
        st.warning("No active query to reflect on")
        return None
    
    try:
        response = requests.post(
            f"{API_URL}/reflect",
            json={"query_id": st.session_state.last_response['query_id']}
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Reflection Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None

def display_document(doc, index):
    """Display a document with metadata"""
    st.markdown(f"""
    <div style="
        padding: 12px;
        margin-bottom: 15px;
        border-left: 3px solid #4e8cff;
        background-color: #f8f9fa;
        border-radius: 0 8px 8px 0;
    ">
        <h4 style="margin-top: 0;">Reference {index + 1} (Score: {doc['score']:.2f})</h4>
        <p>{doc["text"]}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display metadata if available
    if doc.get("metadata"):
        meta = doc["metadata"]
        cols = st.columns(3)
        if meta.get("source"):
            cols[0].caption(f"📄 {meta['source']}")
        if meta.get("page"):
            cols[1].caption(f"📖 Page {meta['page']}")
        if meta.get("article"):
            cols[2].caption(f"⚖️ Article {meta['article']}")

# UI Layout
st.set_page_config(
    page_title="Tunisian Legal Assistant",
    page_icon="⚖️",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stChatMessage {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .user-message {
        background-color: #f0f2f6;
    }
    .assistant-message {
        background-color: #e6f7ff;
    }
    .feedback-section {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 8px;
        margin-top: 20px;
    }
    .settings-section {
        background-color: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
    }
    .stButton button {
        width: 100%;
    }
    .reference-header {
        margin-top: 20px !important;
        margin-bottom: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar for settings and info
with st.sidebar:
    st.title("⚙️ Settings")
    
    with st.expander("Model Configuration", expanded=True):
        st.session_state.model_settings["temperature"] = st.slider(
            "Temperature", 0.1, 1.0, 0.7, 0.1,
            help="Controls randomness (lower = more deterministic)"
        )
        st.session_state.model_settings["max_tokens"] = st.slider(
            "Max Response Length", 50, 500, 150, 50,
            help="Maximum number of tokens in generated response"
        )
        st.session_state.model_settings["top_k"] = st.slider(
            "Reference Documents", 1, 5, 3,
            help="Number of legal documents to reference"
        )
        st.session_state.model_settings["enable_reflection"] = st.checkbox(
            "Enable Self-Reflection", True,
            help="Allow the model to analyze its own responses"
        )
    
    with st.expander("Document Selection", expanded=True):
        selected_field = st.selectbox(
            "Legal Domain", LEGAL_FIELDS,
            help="Select which legal documents to search"
        )
        selected_language = st.selectbox(
            "Response Language", LANGUAGES,
            help="Language for generated responses"
        )
    
    if st.button("Clear Conversation"):
        st.session_state.conversation = []
        st.session_state.current_query_id = None
        st.session_state.last_response = None
        st.rerun()
    
    st.markdown("---")
    st.title("📊 Statistics")
    
    try:
        stats = requests.get(f"{API_URL}/stats").json()
        
        col1, col2 = st.columns(2)
        col1.metric("Total Queries", stats["queries_processed"])
        col2.metric("Documents Loaded", sum(stats["documents_loaded"].values()))
        
        st.subheader("Feedback")
        feedback_cols = st.columns(3)
        feedback_cols[0].metric("👍 Positive", stats["feedback_stats"]["positive"])
        feedback_cols[1].metric("👎 Negative", stats["feedback_stats"]["negative"])
        feedback_cols[2].metric("✏️ Corrections", stats["feedback_stats"]["corrections"])
        
    except Exception as e:
        st.warning(f"Couldn't load statistics: {str(e)}")

# Main chat interface
st.title("🇹🇳 Tunisian Legal Assistant")
st.markdown("Ask questions about Tunisian criminal law or constitution")

# Display conversation history
for message in st.session_state.conversation:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message.get("sources"):
            st.markdown("### 📚 Reference Documents", unsafe_allow_html=True)
            for i, doc in enumerate(message["sources"]):
                display_document(doc, i)
        
        if message.get("reflection") and st.session_state.model_settings["enable_reflection"]:
            with st.expander("🤔 Model Self-Reflection"):
                st.markdown(message["reflection"])

# User input
if prompt := st.chat_input("Ask a legal question..."):
    if len(prompt.strip()) < 3:
        st.warning("Please enter a meaningful question (at least 3 characters)")
        st.stop()
    
    # Add user message to chat
    st.session_state.conversation.append({"role": "user", "content": prompt})
    
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get assistant response
    with st.spinner("🔍 Searching legal documents..."):
        response = send_query(
            query=prompt,
            field=selected_field,
            language=selected_language
        )
        
        if response:
            # Display assistant response
            with st.chat_message("assistant"):
                st.markdown(response["answer"])
                
                # Display sources
                st.markdown("### 📚 Reference Documents", unsafe_allow_html=True)
                for i, doc in enumerate(response["retrieved_documents"]):
                    display_document(doc, i)
                
                # Display reflection if enabled and available
                if response.get("reflection") and st.session_state.model_settings["enable_reflection"]:
                    with st.expander("🤔 Model Self-Reflection"):
                        st.markdown(response["reflection"])
            
            # Add to conversation history
            st.session_state.conversation.append({
                "role": "assistant",
                "content": response["answer"],
                "sources": response["retrieved_documents"],
                "reflection": response.get("reflection")
            })

# Feedback section
if (st.session_state.get('last_response') and 
    st.session_state.conversation and 
    st.session_state.conversation[-1]["role"] == "assistant" and
    st.session_state.last_response['query_id'] not in st.session_state.feedback_given):
    
    st.markdown("---")
    st.subheader("💬 Provide Feedback")
    
    feedback_cols = st.columns([1,1,1,2])
    
    with feedback_cols[0]:
        if st.button("👍 Positive", help="The response was accurate and helpful"):
            submit_feedback(FeedbackType.POSITIVE)
    
    with feedback_cols[1]:
        if st.button("👎 Negative", help="The response was inaccurate or unhelpful"):
            submit_feedback(FeedbackType.NEGATIVE)
    
    with feedback_cols[2]:
        if st.button("🔄 Reflect", help="Get the model's self-assessment"):
            reflection = get_reflection()
            if reflection:
                st.session_state.conversation[-1]["reflection"] = reflection["reflection"]
                st.rerun()
    
    # Correction form
    with st.form("correction_form"):
        correction = st.text_area(
            "✏️ Provide a corrected answer",
            help="If the response was incorrect, please provide the correct answer"
        )
        comments = st.text_input(
            "💬 Additional comments (optional)",
            help="Any additional feedback about the response"
        )
        
        if st.form_submit_button("Submit Correction"):
            if correction:
                if submit_feedback(FeedbackType.CORRECTION, correction, comments):
                    # Update the conversation with the correction
                    st.session_state.conversation[-1]["content"] = correction
                    st.rerun()
            else:
                st.warning("Please provide a corrected answer")

# System status in sidebar footer
with st.sidebar:
    st.markdown("---")
    try:
        status = requests.get(f"{API_URL}/stats").status_code
        if status == 200:
            st.success("🟢 API Connected")
        else:
            st.warning("🟠 API Connection Issues")
    except:
        st.error("🔴 API Offline")

    st.caption(f"v2.0.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")