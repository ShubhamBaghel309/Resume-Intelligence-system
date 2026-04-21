import json
import os
import sqlite3
import uuid


PRIMARY_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resumes.db"
)
FALLBACK_CHAT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "chat_history.db"
)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            search_type TEXT,
            query_analysis TEXT,
            candidate_names TEXT,
            conversation_context TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS message_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            resume_id TEXT,
            rank INTEGER,
            FOREIGN KEY (message_id) REFERENCES chat_messages(message_id)
        )
        """,
    ]


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _init_chat_db(db_path: str) -> None:
    _ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for statement in _schema_statements():
        cursor.execute(statement)
    _ensure_column(conn, "chat_messages", "conversation_context", "TEXT")
    conn.commit()
    conn.close()


def _can_write_to_db(db_path: str) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("CREATE TABLE IF NOT EXISTS __chat_write_probe (id INTEGER)")
        cursor.execute("DROP TABLE IF EXISTS __chat_write_probe")
        conn.rollback()
        conn.close()
        return True
    except sqlite3.OperationalError:
        return False
    except Exception:
        return False


def _resolve_chat_db_path() -> str:
    configured_path = os.getenv("CHAT_DB_PATH")
    if configured_path:
        _init_chat_db(configured_path)
        return configured_path

    if os.path.exists(PRIMARY_DB_PATH) and _can_write_to_db(PRIMARY_DB_PATH):
        _init_chat_db(PRIMARY_DB_PATH)
        return PRIMARY_DB_PATH

    _init_chat_db(FALLBACK_CHAT_DB_PATH)
    return FALLBACK_CHAT_DB_PATH


DB_PATH = _resolve_chat_db_path()


def _connect() -> sqlite3.Connection:
    _init_chat_db(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_chat_session(title: str = "New Conversation") -> str:
    """
    Create a new chat session

    Args:
        title: Optional title for the conversation

    Returns:
        session_id: Unique ID for this session
    """
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_sessions (session_id, title, created_at, last_updated_at)
        VALUES (?, ?, datetime('now'), datetime('now'))
        """,
        (session_id, title),
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

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_messages (message_id, session_id, role, content, timestamp)
        VALUES (?, ?, 'user', ?, datetime('now'))
        """,
        (message_id, session_id, content),
    )

    cursor.execute(
        """
        UPDATE chat_sessions
        SET last_updated_at = datetime('now')
        WHERE session_id = ?
        """,
        (session_id,),
    )

    conn.commit()
    conn.close()

    return message_id


def save_agent_message(
    session_id: str,
    content: str,
    candidate_ids: list = None,
    candidate_names: list = None,
    search_type: str = None,
    query_analysis: dict = None,
    conversation_context: dict = None,
) -> str:
    """
    Save agent message to database

    Args:
        session_id: Which conversation
        content: Agent's answer
        candidate_ids: List of resume IDs that were returned
        candidate_names: List of candidate names
        search_type: "sql", "vector", or "hybrid"
        query_analysis: Dict with query type, strategy, etc.

    Returns:
        message_id: Unique ID for this message
    """
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    query_analysis_json = json.dumps(query_analysis) if query_analysis else None
    candidate_names_json = json.dumps(candidate_names) if candidate_names else None
    conversation_context_json = json.dumps(conversation_context) if conversation_context else None

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_messages (message_id, session_id, role, content, timestamp, search_type, query_analysis, candidate_names, conversation_context)
        VALUES (?, ?, 'agent', ?, datetime('now'), ?, ?, ?, ?)
        """,
        (
            message_id,
            session_id,
            content,
            search_type,
            query_analysis_json,
            candidate_names_json,
            conversation_context_json,
        ),
    )

    if candidate_ids:
        for rank, resume_id in enumerate(candidate_ids, start=1):
            cursor.execute(
                """
                INSERT INTO message_results (message_id, resume_id, rank)
                VALUES (?, ?, ?)
                """,
                (message_id, resume_id, rank),
            )

    cursor.execute(
        """
        UPDATE chat_sessions
        SET last_updated_at = datetime('now')
        WHERE session_id = ?
        """,
        (session_id,),
    )

    conn.commit()
    conn.close()

    return message_id


def load_chat_history(session_id: str, limit: int = 10) -> list:
    """
    Load chat history from database

    Args:
        session_id: Which conversation to load
        limit: Maximum number of recent messages to load

    Returns:
        List of message dicts with keys: role, content, candidate_ids, timestamp
    """
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT message_id, role, content, timestamp, search_type, query_analysis, candidate_names, conversation_context
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (session_id, limit),
    )

    messages = list(reversed(cursor.fetchall()))

    chat_history = []
    for msg in messages:
        message_dict = {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"],
        }

        if msg["role"] == "agent":
            cursor.execute(
                """
                SELECT resume_id
                FROM message_results
                WHERE message_id = ?
                ORDER BY rank
                """,
                (msg["message_id"],),
            )
            candidate_rows = cursor.fetchall()
            message_dict["candidate_ids"] = [row["resume_id"] for row in candidate_rows]

            if msg["candidate_names"]:
                message_dict["candidate_names"] = json.loads(msg["candidate_names"])
            if msg["conversation_context"]:
                message_dict["conversation_context"] = json.loads(msg["conversation_context"])

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
    conn = _connect()
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


if __name__ == "__main__":
    print("Testing chat_manager.py...")
    print(f"Using DB: {DB_PATH}")

    session_id = create_chat_session("Test Conversation")
    print(f"Created session: {session_id}")

    msg1 = save_user_message(session_id, "Find Python developers")
    print(f"Saved user message: {msg1}")

    msg2 = save_agent_message(
        session_id=session_id,
        content="Found 3 Python developers...",
        candidate_ids=["resume_abc", "resume_xyz"],
        search_type="hybrid",
        query_analysis={"query_type": "skill_based", "confidence": 0.95},
    )
    print(f"Saved agent message: {msg2}")
