import streamlit as st
import sys
from pathlib import Path
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.workflows.intelligent_agent import ResumeIntelligenceAgent
from app.chat.chat_manager import get_all_sessions, load_chat_history
import sqlite3

# Page config
st.set_page_config(
    page_title="Resume Intelligence System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .agent-message {
        background-color: #f5f5f5;
    }
    .candidate-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .candidate-name {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1976d2;
    }
    .candidate-detail {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.25rem;
    }
    .stTextInput input {
        border: 2px solid #1976d2;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = None  # Will be initialized after API keys provided
    
if "session_id" not in st.session_state:
    st.session_state.session_id = None
    
if "messages" not in st.session_state:
    st.session_state.messages = []

if "candidate_results" not in st.session_state:
    st.session_state.candidate_results = []

if "conversation_context" not in st.session_state:
    st.session_state.conversation_context = {}

if "api_keys_set" not in st.session_state:
    st.session_state.api_keys_set = False

# Sidebar
with st.sidebar:
    st.title("🤖 Resume Intelligence")
    st.markdown("---")
    
    # API Keys Section
    st.subheader("🔑 API Configuration")
    
    with st.expander("⚙️ Configure API Keys", expanded=not st.session_state.api_keys_set):
        st.info("💡 **Tip**: If changing keys, use the 'Force Reload' button below for best results")
        
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Required for LangGraph agent and MCP email generation"
        )
        
        groq_api_key = st.text_input(
            "Groq API Key (Optional)",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
            help="Get your free API key from https://console.groq.com"
        )
        
        gemini_api_key = st.text_input(
            "Gemini API Key (Optional)",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
            help="Get your free API key from https://aistudio.google.com/app/apikey"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save & Initialize", use_container_width=True):
                if openai_api_key.strip():
                    # Set environment variables
                    os.environ["OPENAI_API_KEY"] = openai_api_key.strip()
                    if groq_api_key.strip():
                        os.environ["GROQ_API_KEY"] = groq_api_key.strip()
                    if gemini_api_key.strip():
                        os.environ["GEMINI_API_KEY"] = gemini_api_key.strip()
                    
                    # Reinitialize agent with new API keys
                    try:
                        # Force reimport to pick up new env vars
                        import importlib
                        import sys
                        
                        # Remove cached modules
                        modules_to_reload = [
                            'app.workflows.intelligent_agent',
                            'app.generation.answer_generation',
                            'app.parsing.resume_parser'
                        ]
                        
                        for module_name in modules_to_reload:
                            if module_name in sys.modules:
                                del sys.modules[module_name]
                        
                        from app.workflows import intelligent_agent
                        
                        st.session_state.agent = intelligent_agent.ResumeIntelligenceAgent()
                        st.session_state.api_keys_set = True
                        st.success("✅ Agent initialized successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to initialize agent: {str(e)}")
                else:
                    st.warning("⚠️ Please provide at least the OpenAI API key")
        
        with col2:
            if st.button("🔄 Force Reload", use_container_width=True, type="secondary"):
                if openai_api_key.strip():
                    # Nuclear option: clear everything
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    
                    # Update environment
                    os.environ["OPENAI_API_KEY"] = openai_api_key.strip()
                    if groq_api_key.strip():
                        os.environ["GROQ_API_KEY"] = groq_api_key.strip()
                    if gemini_api_key.strip():
                        os.environ["GEMINI_API_KEY"] = gemini_api_key.strip()
                    
                    # Clear all session state
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    
                    st.success("✅ Reloading with new API keys...")
                    st.rerun()
                else:
                    st.warning("⚠️ Please provide API keys first")
    
    if st.session_state.api_keys_set:
        st.success("✅ API Keys Configured")
    else:
        st.warning("⚠️ Please configure API keys to start")
    
    st.markdown("---")
    
    # New Chat Button (only if agent is initialized)
    if st.session_state.api_keys_set:
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.session_state.candidate_results = []
            st.session_state.conversation_context = {}
            st.rerun()
        
        st.markdown("---")
        st.subheader("📜 Chat History")
        
        # Load all sessions
        try:
            sessions = get_all_sessions()
            if sessions:
                for session in sessions[:10]:  # Show last 10 sessions
                    session_id = session['session_id']
                    title = session['title'][:30] + "..." if len(session['title']) > 30 else session['title']
                    
                    # Button to load this session
                    if st.button(
                        f"💬 {title}",
                        key=f"session_{session_id}",
                        use_container_width=True
                    ):
                        st.session_state.session_id = session_id
                        # Load messages from database
                        st.session_state.messages = load_chat_history(session_id, limit=50)
                        st.session_state.candidate_results = []
                        st.session_state.conversation_context = {}
                        st.rerun()
            else:
                st.info("No previous chats")
        except Exception as e:
            st.warning("Could not load chat history")
        
        st.markdown("---")
        
        # Stats
        st.subheader("📊 System Stats")
        try:
            conn = sqlite3.connect("resumes.db")
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
            total_resumes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chat_sessions")
            total_chats = cursor.fetchone()[0]
            
            conn.close()
            
            st.metric("Total Resumes", total_resumes)
            st.metric("Total Chats", total_chats)
        except:
            pass

# Main content
st.markdown('<div class="main-header">💼 Resume Intelligence Assistant</div>', unsafe_allow_html=True)

# Check if agent is initialized
if not st.session_state.api_keys_set:
    st.warning("⚠️ Please configure your API keys in the sidebar to get started")
    st.info("""
    ### Getting Started:
    
    1. **OpenAI API Key** (Required):
       - Visit [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
       - Sign up and create an API key
       - Paste it in the sidebar (needed for LangGraph agent and MCP email generation)
    
    2. **Groq API Key** (Optional - Fast inference):
       - Visit [https://console.groq.com](https://console.groq.com)
       - Sign up for a free account
       - Create an API key
       - Paste it in the sidebar
    
    3. **Gemini API Key** (Optional - Fallback):
       - Visit [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
       - Create a free API key
       - Paste it in the sidebar
    
    4. Click **"Save & Initialize Agent"**
    
    5. Start chatting!
    
    ### Features:
    - 🔍 **Smart Search**: Find candidates by skills, experience, education, location
    - 📧 **Email Integration**: Send interview invites via MCP servers
    - 💬 **Context-Aware**: Ask follow-up questions about candidates
    - 🎯 **Hybrid Search**: Combines SQL filtering and semantic vector search
    """)
    st.stop()

# Display current session info
if st.session_state.session_id:
    st.info(f"📝 Session: {st.session_state.session_id[:12]}... | {len(st.session_state.messages)} messages")
else:
    st.success("🆕 New conversation - ask me anything about candidates!")

st.markdown("---")

# Display chat messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        
        with st.chat_message(role):
            st.markdown(content)
            
            # Show candidate IDs for agent messages if available
            if role == "agent" and message.get("candidate_ids"):
                candidate_count = len(message["candidate_ids"])
                if candidate_count > 0:
                    st.caption(f"👥 Found {candidate_count} candidate(s)")

# ✅ Show email field collection form if pending
if st.session_state.conversation_context.get("pending_email_action"):
    pending = st.session_state.conversation_context["pending_email_action"]
    missing = pending.get("missing_fields", [])
    
    field_labels = {
        "job_role": "Job Role",
        "company_name": "Company Name",
        "interview_datetime": "Interview Date & Time",
        "interview_location": "Interview Location",
        "interviewer_name": "Interviewer Name"
    }
    field_placeholders = {
        "job_role": "e.g., Machine Learning Intern, Software Developer",
        "company_name": "e.g., Google, Microsoft",
        "interview_datetime": "e.g., March 15 at 2 PM",
        "interview_location": "e.g., Google Meet, Conference Room A",
        "interviewer_name": "e.g., Dr. Sharma, John from HR"
    }
    
    if missing:
        with st.form("email_fields_form"):
            st.markdown("📝 **Fill in the details below:**")
            field_values = {}
            for field_key in missing:
                field_values[field_key] = st.text_input(
                    field_labels.get(field_key, field_key),
                    placeholder=field_placeholders.get(field_key, ""),
                    key=f"email_field_{field_key}"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("📧 Send Email", use_container_width=True, type="primary")
            with col2:
                cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
            
            if submitted:
                # Check all fields filled
                empty_fields = [k for k, v in field_values.items() if not v.strip()]
                if empty_fields:
                    st.error(f"Please fill in: {', '.join(field_labels[f] for f in empty_fields)}")
                else:
                    # Build query with all fields and send to agent
                    parts = [f"{field_labels[k]}: {v.strip()}" for k, v in field_values.items()]
                    combined_query = ", ".join(parts)
                    
                    # Add as user message
                    st.session_state.messages.append({"role": "user", "content": combined_query})
                    
                    with st.spinner("📧 Sending interview invitation..."):
                        try:
                            result = st.session_state.agent.query(
                                user_query=combined_query,
                                session_id=st.session_state.session_id,
                                verbose=False,
                                conversation_context=st.session_state.conversation_context
                            )
                            st.session_state.session_id = result["session_id"]
                            st.session_state.candidate_results = result.get("candidate_ids", [])
                            st.session_state.conversation_context = result.get("conversation_context", {})
                            st.session_state.messages.append({
                                "role": "agent",
                                "content": result["answer"],
                                "candidate_ids": result.get("candidate_ids", [])
                            })
                        except Exception as e:
                            st.session_state.messages.append({
                                "role": "agent",
                                "content": f"❌ Error: {str(e)}"
                            })
                    st.rerun()
            
            if cancelled:
                st.session_state.conversation_context = {}
                st.session_state.messages.append({
                    "role": "agent",
                    "content": "❌ Email sending cancelled."
                })
                st.rerun()

# Chat input
user_input = st.chat_input("Ask me about candidates... (e.g., 'Find Python developers with 5+ years experience')")

if user_input:
    # ✅ Handle greetings in frontend (no agent call needed)
    greeting_keywords = ["hi", "hello", "hey", "good morning", "good afternoon", 
                        "good evening", "greetings", "namaste", "hola", "sup", "yo"]
    
    user_input_lower = user_input.lower().strip()
    is_greeting = (
        len(user_input.split()) <= 3 and 
        any(word in user_input_lower for word in greeting_keywords)
    )
    
    if is_greeting:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Display greeting response (no agent call)
        with st.chat_message("assistant"):
            greeting_response = """Hello! 👋 I'm your **Resume Intelligence Assistant**. 

I can help you find candidates based on:
- 🔧 **Skills**: "Find Python developers"
- ⏱️ **Experience**: "Who has 5+ years experience?"
- 🏢 **Companies**: "Show candidates who worked at Google"
- 📚 **Education**: "Find candidates with MBA"
- 📍 **Location**: "Candidates in Bangalore"
- 💼 **Projects**: "Who has worked on Machine Learning projects?"
- 🏆 **Achievements**: "Show me candidates with AWS certifications"

You can also ask follow-up questions like "Show me their skills" or "What are their projects?"

What would you like to know?"""
            
            st.markdown(greeting_response)
        
        st.session_state.messages.append({
            "role": "agent",
            "content": greeting_response,
            "candidate_ids": []
        })
        
        st.rerun()
    
    # Regular query - call agent
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Add to messages
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    # Get agent response
    with st.chat_message("assistant"):
        # Check if this is an email sending action or email field continuation
        is_email_action = any(keyword in user_input.lower() for keyword in [
            "send interview", "send email", "send invite", "email interview"
        ]) or st.session_state.conversation_context.get("pending_email_action")
        
        spinner_text = "📧 Processing email details..." if is_email_action else "🔍 Searching resumes..."
        
        with st.spinner(spinner_text):
            try:
                result = st.session_state.agent.query(
                    user_query=user_input,
                    session_id=st.session_state.session_id,
                    verbose=False,  # Disable console output
                    conversation_context=st.session_state.conversation_context
                )
                
                # Update session ID
                st.session_state.session_id = result["session_id"]
                
                # Display answer
                st.markdown(result["answer"])
                
                # Store candidate results and conversation context
                st.session_state.candidate_results = result.get("candidate_ids", [])
                st.session_state.conversation_context = result.get("conversation_context", {})
                
                # Add to messages
                st.session_state.messages.append({
                    "role": "agent",
                    "content": result["answer"],
                    "candidate_ids": result.get("candidate_ids", [])
                })
                
                # Show candidate count or email status
                if result.get("email_sent"):
                    st.success("✅ Email(s) sent successfully!")
                elif result.get("candidate_ids"):
                    st.caption(f"👥 Found {len(result['candidate_ids'])} candidate(s)")
                
            except Exception as e:
                error_msg = str(e)
                if "GROQ_API_KEY" in error_msg or "api" in error_msg.lower():
                    st.error("❌ API Key Error. Please check your API keys in the sidebar.")
                elif "MCP" in error_msg or "mcp" in error_msg.lower():
                    st.error("❌ MCP Server Error. Make sure MCP dependencies are installed: pip install mcp fastmcp")
                else:
                    st.error(f"❌ Error: {error_msg}")
                
                st.session_state.messages.append({
                    "role": "agent",
                    "content": f"Sorry, I encountered an error: {error_msg}"
                })
    
    # Rerun to update chat
    st.rerun()

# Candidate Details Section (expandable)
if st.session_state.candidate_results:
    st.markdown("---")
    with st.expander(f"👥 View {len(st.session_state.candidate_results)} Candidate Details", expanded=False):
        try:
            conn = sqlite3.connect("resumes.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            for resume_id in st.session_state.candidate_results[:10]:  # Show first 10
                cursor.execute("""
                    SELECT candidate_name, email, phone, location, 
                           total_experience_years, current_role, skills
                    FROM parsed_resumes
                    WHERE resume_id = ?
                """, (resume_id,))
                
                row = cursor.fetchone()
                if row:
                    st.markdown(f"""
                    <div class="candidate-card">
                        <div class="candidate-name">👤 {row['candidate_name']}</div>
                        <div class="candidate-detail">📧 {row['email'] or 'N/A'} | 📱 {row['phone'] or 'N/A'}</div>
                        <div class="candidate-detail">📍 {row['location'] or 'N/A'} | 💼 {row['current_role'] or 'N/A'}</div>
                        <div class="candidate-detail">⏱️ {row['total_experience_years'] or 0} years experience</div>
                        <div class="candidate-detail">🔧 Skills: {row['skills'][:200] if row['skills'] else 'N/A'}{'...' if row['skills'] and len(row['skills']) > 200 else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            conn.close()
        except Exception as e:
            st.error(f"Could not load candidate details: {e}")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
    "Resume Intelligence System v2.5 | Powered by LangGraph + ChromaDB + OpenAI + MCP Servers"
    "</div>",
    unsafe_allow_html=True
)