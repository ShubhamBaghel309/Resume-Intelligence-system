import sqlite3
import uuid
import json
import os

# Use absolute path (same pattern as intelligent_agent.py)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resumes.db")


def create_chat_session(title: str = "New Conversation") -> str:
    """
    Create a new chat session
    
    Args:
        title: Optional title for the conversation
        
    Returns:
        session_id: Unique ID for this session
    """
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO chat_sessions (session_id, title, created_at, last_updated_at)
        VALUES (?, ?, datetime('now'), datetime('now'))
        """,
        (session_id, title)
    )
    
    conn.commit()
    conn.close()
    
    return session_id


def save_user_message(session_id: str, content: str) -> str:
    """
    Save user message to database
    
    Args:
        session_id: Which conversation this belongs to
        content: What the user said
        
    Returns:
        message_id: Unique ID for this message
    """
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO chat_messages (message_id, session_id, role, content, timestamp)
        VALUES (?, ?, 'user', ?, datetime('now'))
        """,
        (message_id, session_id, content)
    )
    
    # Update session's last_updated_at
    cursor.execute(
        """
        UPDATE chat_sessions 
        SET last_updated_at = datetime('now')
        WHERE session_id = ?
        """,
        (session_id,)
    )
    
    conn.commit()
    conn.close()
    
    return message_id


def save_agent_message(session_id: str, content: str, candidate_ids: list = None, 
                       candidate_names: list = None, search_type: str = None, 
                       query_analysis: dict = None) -> str:
    """
    Save agent message to database
    
    Args:
        session_id: Which conversation
        content: Agent's answer
        candidate_ids: List of resume IDs that were returned
        candidate_names: List of candidate names (e.g., ["Rosy Yuniar", "Ratish Nair"])
        search_type: "sql", "vector", or "hybrid"
        query_analysis: Dict with query type, strategy, etc.
        
    Returns:
        message_id: Unique ID for this message
    """
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    
    # Convert lists/dicts to JSON
    query_analysis_json = json.dumps(query_analysis) if query_analysis else None
    candidate_names_json = json.dumps(candidate_names) if candidate_names else None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert agent message
    cursor.execute(
        """
        INSERT INTO chat_messages (message_id, session_id, role, content, timestamp, search_type, query_analysis, candidate_names)
        VALUES (?, ?, 'agent', ?, datetime('now'), ?, ?, ?)
        """,
        (message_id, session_id, content, search_type, query_analysis_json, candidate_names_json)
    )
    
    # Insert candidate IDs into message_results table (if any)
    if candidate_ids:
        for rank, resume_id in enumerate(candidate_ids, start=1):
            cursor.execute(
                """
                INSERT INTO message_results (message_id, resume_id, rank)
                VALUES (?, ?, ?)
                """,
                (message_id, resume_id, rank)
            )
    
    # Update session's last_updated_at
    cursor.execute(
        """
        UPDATE chat_sessions 
        SET last_updated_at = datetime('now')
        WHERE session_id = ?
        """,
        (session_id,)
    )
    
    conn.commit()
    conn.close()
    
    return message_id


def load_chat_history(session_id: str, limit: int = 10) -> list:
    """
    Load chat history from database
    
    Args:
        session_id: Which conversation to load
        limit: Maximum number of recent messages to load (default 10)
        
    Returns:
        List of message dicts with keys: role, content, candidate_ids, timestamp
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    cursor = conn.cursor()
    
    # Load messages ordered by timestamp (oldest first for context)
    cursor.execute(
        """
        SELECT message_id, role, content, timestamp, search_type, query_analysis, candidate_names
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (session_id, limit)
    )
    
    messages = cursor.fetchall()
    
    # Reverse to get chronological order (oldest → newest)
    messages = list(reversed(messages))
    
    # Build result list
    chat_history = []
    for msg in messages:
        message_dict = {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"]
        }
        
        # For agent messages, load associated candidate_ids and names
        if msg["role"] == "agent":
            cursor.execute(
                """
                SELECT resume_id 
                FROM message_results
                WHERE message_id = ?
                ORDER BY rank
                """,
                (msg["message_id"],)
            )
            candidate_rows = cursor.fetchall()
            message_dict["candidate_ids"] = [row["resume_id"] for row in candidate_rows]
            
            # Add candidate names if available
            if msg["candidate_names"]:
                message_dict["candidate_names"] = json.loads(msg["candidate_names"])
            
            # Add search metadata
            if msg["search_type"]:
                message_dict["search_type"] = msg["search_type"]
            if msg["query_analysis"]:
                message_dict["query_analysis"] = json.loads(msg["query_analysis"])
        
        chat_history.append(message_dict)
    
    conn.close()
    
    return chat_history


def get_all_sessions() -> list:
    """
    Get list of all chat sessions
    
    Returns:
        List of session dicts with session_id, title, created_at, last_updated_at
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT session_id, title, created_at, last_updated_at
        FROM chat_sessions
        ORDER BY last_updated_at DESC
        """
    )
    
    sessions = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return sessions


# ============= Testing Functions =============

if __name__ == "__main__":
    # Test the functions
    print("Testing chat_manager.py...")
    
    # Create session
    session_id = create_chat_session("Test Conversation")
    print(f"✅ Created session: {session_id}")
    
    # Save user message
    msg1 = save_user_message(session_id, "Find Python developers")
    print(f"✅ Saved user message: {msg1}")
    
    # Save agent message
    msg2 = save_agent_message(
        session_id=session_id,
        content="Found 3 Python developers...",
        candidate_ids=["resume_abc", "resume_xyz"],
        search_type="hybrid",
        query_analysis={"query_type": "skill_based", "confidence": 0.95}
    )
    print(f"✅ Saved agent message: {msg2}")
    
    # Load history
    history = load_chat_history(session_id)
    print(f"✅ Loaded {len(history)} messages:")
    for msg in history:
        print(f"   {msg['role']}: {msg['content'][:100]}...")
    
    print("\n✅ All tests passed!")