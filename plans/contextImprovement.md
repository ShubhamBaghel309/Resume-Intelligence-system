# Plan: ChatGPT/Claude-Level Context Management

> **TL;DR** — Replace the fragile, in-memory `conversation_context` dict with a structured,
> persistent memory system that tracks entities, topics, tool history, and topic shifts across
> turns. The agent will understand *what* was discussed, *who* was referenced, and *when*
> the user changes subject — just like ChatGPT/Claude do. Backend-only; no Streamlit changes.

---

## Architecture Overview

### Current State (Problems)

| Problem | Where | Impact |
|---------|-------|--------|
| `conversation_context` is an untyped `dict` | Everywhere | Silent key errors, no IDE help |
| Context lives in caller's RAM only | Streamlit/CLI → `query()` | Lost on page reload, crash, session switch |
| `last_tool_response` never cleared | `execute_mcp_tool_node` L1716 | Unrelated queries misrouted as tool follow-ups |
| No topic shift detection | `route_after_analysis` L2013 | "find Python devs" after GitHub check → routed to tool follow-up |
| Pronoun resolution = raw text in LLM prompt | `analyze_query_node` L495 | LLM sometimes ignores the candidate list |
| No entity tracking across turns | Whole system | Can't reference "the 3rd candidate" or "that company" |
| History limit hardcoded to 10 | `load_chat_history` L135 | No flexibility |
| No structured memory of *what happened* | Whole system | Agent can't say "earlier you searched for X and found Y" |

### Target State

```
┌─────────────────────────────────────────────────────┐
│                  ConversationMemory                  │
│  (Pydantic model, persisted to DB per session)      │
├─────────────────────────────────────────────────────┤
│ active_entities: EntityTracker                       │
│   - candidates: [{id, name, source, turn}]          │
│   - tools: [{server_id, name, last_query, turn}]    │
│   - topics: [{label, turn_started, turn_ended}]     │
│   - custom_refs: {key → value}  (repo names, etc.)  │
│                                                      │
│ current_topic: TopicState                            │
│   - label: str  ("github_profile", "candidate_search") │
│   - context_type: "tool" | "search" | "general"     │
│   - started_at_turn: int                             │
│   - data_snapshot: dict  (last_tool_response / last  │
│     search results summary)                          │
│                                                      │
│ turn_counter: int                                    │
│ pending_action: PendingAction | None                 │
│ summary: str  (rolling summary of older turns)       │
│ topic_history: [TopicState]  (completed topics)      │
└─────────────────────────────────────────────────────┘
```

---

## Steps

### Step 1: Define `ConversationMemory` Pydantic Models

**New file:** `app/models/conversation_memory.py`

Define these models:

- `TrackedEntity` — `id: str`, `name: str`, `entity_type: Literal["candidate", "tool", "topic", "reference"]`, `source: str` (which turn/action created it), `turn_added: int`, `metadata: dict = {}`
- `TopicState` — `label: str`, `context_type: Literal["tool", "search", "general", "greeting"]`, `started_at_turn: int`, `ended_at_turn: int | None = None`, `data_snapshot: dict = {}` (stores last_tool_response or search result summary)
- `PendingAction` — `server_id: str`, `collected_fields: dict`, `candidates: list`, `missing_fields: list`
- `EntityTracker` — `candidates: list[TrackedEntity] = []`, `tools: list[TrackedEntity] = []`, `references: dict[str, Any] = {}` (e.g., "MiniGPT" → repo ref)
  - Methods: `add_candidate(id, name, turn)`, `add_tool(server_id, name, turn)`, `add_reference(key, value, turn)`, `get_active_candidates(max_turns_ago=5)`, `get_most_recent_candidate()`, `clear_stale(current_turn, ttl=10)`
- `ConversationMemory` — `session_id: str`, `turn_counter: int = 0`, `entities: EntityTracker`, `current_topic: TopicState | None`, `topic_history: list[TopicState]`, `pending_action: PendingAction | None`, `summary: str = ""`, `raw_last_tool_response: dict | None = None`
  - Methods: `bump_turn()`, `start_topic(label, context_type, data_snapshot)`, `end_current_topic()`, `is_topic_active(label)`, `serialize() → str` (JSON), `@classmethod deserialize(json_str) → ConversationMemory`, `get_context_for_llm() → str` (formatted string for prompts)

**Why Pydantic:** schema enforcement, serialization for DB, IDE autocomplete, `.model_dump_json()` / `.model_validate_json()` for free.

**References:** Current untyped dict keys at `intelligent_agent.py L1719` (`last_tool_response`), `L1683` (`pending_tool_action`), `L510` (`candidate_ids`, `candidate_names`).

---

### Step 2: Add `conversation_memory` Column to DB

**File:** `app/db/init_db.py` — lines 11–17

Add a new column to `chat_sessions`:

```sql
ALTER TABLE chat_sessions ADD COLUMN conversation_memory TEXT DEFAULT '{}';
```

Add migration logic: in `initialize_database()`, after creating tables, run an `ALTER TABLE` wrapped in try/except (column may already exist). This stores the serialized `ConversationMemory` JSON per session.

**File:** `app/chat/chat_manager.py`

Add two new functions:
- `save_conversation_memory(session_id: str, memory: ConversationMemory)` — UPDATE `chat_sessions SET conversation_memory = ? WHERE session_id = ?`
- `load_conversation_memory(session_id: str) → ConversationMemory | None` — SELECT, deserialize, return. If column is empty/`'{}'`, return a fresh `ConversationMemory(session_id=session_id)`.

**Why session-level, not message-level:** Memory is a rolling state that evolves each turn. Storing it per-session (updated after each turn) is simpler and mirrors how ChatGPT works — you don't version memory per message.

---

### Step 3: Replace `conversation_context: dict` with `ConversationMemory` in AgentState

**File:** `app/workflows/intelligent_agent.py` — AgentState at L27

Change:
```python
conversation_context: dict  →  conversation_memory: ConversationMemory
```

Keep `conversation_context` as a deprecated alias for one release cycle (or remove if no external callers depend on it).

**Downstream changes:** Every node that reads/writes `state["conversation_context"]` must be updated to use `state["conversation_memory"]`. Major touch points:

| Node | Lines | What changes |
|------|-------|-------------|
| `analyze_query_node` | L507–L511 | Write `memory.entities.add_candidate()` instead of `existing_ctx["candidate_ids"]` |
| `execute_mcp_tool_node` | L1617, L1683, L1716 | Use `memory.pending_action` and `memory.raw_last_tool_response` |
| `generate_answer_node` | L1770 | Read `memory.raw_last_tool_response` |
| `route_after_analysis` | L2022–L2026 | Read `memory.current_topic` and `memory.raw_last_tool_response` |
| `query()` | L2165 | Load from DB → pass into state; after graph → save back to DB |

---

### Step 4: Implement Topic Shift Detection

**New function** in `app/workflows/intelligent_agent.py` (or `app/models/conversation_memory.py`):

```python
detect_topic_shift(query: str, memory: ConversationMemory, query_analysis: dict) → bool
```

**Logic (3-layer detection):**

1. **Explicit tool switch:** If `query_analysis` triggers a `tool_action` AND the tool's `server_id` ≠ `memory.current_topic.label` → topic shift.

2. **Context type switch:** If current topic is `"tool"` but new query is a candidate search (no tool action, has skill/name filters) → topic shift.

3. **LLM fallback** (for ambiguous cases): Add a lightweight LLM call with a tiny prompt:
   ```
   Current topic: {memory.current_topic.label} ({memory.current_topic.context_type})
   Last discussed: {brief summary}
   New query: {query}
   
   Is this a continuation of the current topic or a new topic?
   Answer: "continuation" or "new_topic"
   ```
   Only invoke this when layers 1-2 are inconclusive (e.g., current topic is "search" and new query also looks like a search but for different criteria).

**On topic shift:**
- Call `memory.end_current_topic()` — moves `current_topic` to `topic_history`, sets `ended_at_turn`
- Clear `memory.raw_last_tool_response` (prevents stale follow-up routing)
- Call `memory.start_topic(new_label, new_context_type, {})`
- Keep `memory.entities` — candidates from previous topics remain accessible (with staleness via `turn_added`)

**Where to call it:** In `analyze_query_node`, after LLM analysis returns `query_analysis`, before MCP tool detection. Insert between L684 (where analysis is written to state) and L694 (where tool action is detected).

---

### Step 5: Update Entity Tracking in `analyze_query_node`

**File:** `app/workflows/intelligent_agent.py` — lines 453–511

Replace the current `most_recent_candidates` logic with `EntityTracker` operations:

1. **On candidate search results:** After `enrich_results_node` or `generate_answer_node` produces `final_results`, call:
   ```python
   for candidate in final_results:
       memory.entities.add_candidate(candidate["resume_id"], candidate["candidate_name"], memory.turn_counter)
   ```

2. **On tool execution:** In `execute_mcp_tool_node`, after successful execution:
   ```python
   memory.entities.add_tool(server_id, server_name, memory.turn_counter)
   ```

3. **On reference extraction:** When GitHub tool returns repos, or JD generator returns a description, extract key references:
   ```python
   # After GitHub tool:
   for repo in resp.get("top_repos", []):
       memory.entities.add_reference(repo["name"], {"type": "repo", "url": repo["url"], "language": repo["language"]}, memory.turn_counter)
   ```

4. **Pronoun resolution upgrade:** Replace the raw `MOST RECENT CANDIDATES` text block in the LLM prompt (L495–L504) with structured output from `memory.get_context_for_llm()`:
   ```
   📌 ACTIVE CONTEXT (turn {N}):
   
   CURRENT TOPIC: GitHub Profile Check for @torvalds
   
   TRACKED CANDIDATES (most recent first):
   1. Linus Torvalds (ID: xxx) — from turn 3 (GitHub profile check)
   2. Shubham Baghel (ID: yyy) — from turn 1 (resume search)
   
   TRACKED REFERENCES:
   - "MiniGPT" → GitHub repo (Python, github.com/...)
   - "linux" → GitHub repo (C, github.com/...)
   
   RECENT TOOL RESULTS:
   - GitHub Profile Checker (turn 3): 11 repos, top langs: C, OpenSCAD, C++
   ```

This gives the LLM much richer context for pronoun resolution and follow-up detection.

---

### Step 6: Fix Follow-Up Routing with Topic Awareness

**File:** `app/workflows/intelligent_agent.py` — route_after_analysis at L2013

Replace the current logic:
```python
# Current (too broad):
if last_tool and not tool_action:
    return "generate_answer"
```

With topic-aware routing:
```python
memory = state["conversation_memory"]

# 1. If there's a new tool action → execute it (topic shift already handled in analyze)
if tool_action:
    if tool_action.get("needs_candidate_search"):
        return "sql_filter"
    return "execute_mcp_tool"

# 2. If current topic is a tool AND we have tool data → follow-up
if (memory.current_topic
    and memory.current_topic.context_type == "tool"
    and memory.raw_last_tool_response):
    return "generate_answer"

# 3. Q&A about previous candidates
if analysis.get("is_qa_query"):
    return "fetch_context_candidates"

# 4. Default: new search
return "sql_filter"
```

This prevents the "GitHub follow-up absorbs all queries" bug because topic shift detection (Step 4) will have already cleared `current_topic` and `raw_last_tool_response` if the user switched subjects.

---

### Step 7: Upgrade `generate_answer_node` Follow-Up Handler

**File:** `app/workflows/intelligent_agent.py` — lines 1770–1795

Replace inline LLM instantiation with a richer prompt that includes full topic context:

```python
memory = state["conversation_memory"]
if memory.current_topic and memory.current_topic.context_type == "tool" and memory.raw_last_tool_response:
    # Build context from memory, not just raw JSON
    context_str = memory.get_context_for_llm()  # structured entity/reference info
    # Use module-level LLM (not inline instantiation)
    answer = llm.invoke([
        SystemMessage(content="You answer follow-up questions about tool results. "
                             "Use the data and tracked references below. Be concise."),
        HumanMessage(content=f"{context_str}\n\n"
                            f"Tool response data:\n{json.dumps(memory.raw_last_tool_response['response'], indent=2)}\n\n"
                            f"Follow-up question: {state['query']}")
    ]).content
```

Also reference `memory.entities.references` so the LLM knows about tracked repo names, companies, etc.

---

### Step 8: Persist Memory in `query()` Method

**File:** `app/workflows/intelligent_agent.py` — query() at L2117

**Before graph invocation:**
```python
# Load or create memory
if session_id:
    memory = load_conversation_memory(session_id)
    if not memory:
        memory = ConversationMemory(session_id=session_id)
else:
    session_id = create_chat_session(title=user_query)
    memory = ConversationMemory(session_id=session_id)

memory.bump_turn()
# Put into initial state
initial_state["conversation_memory"] = memory
```

**After graph invocation:**
```python
# Extract updated memory from final state and persist
final_memory = final_state["conversation_memory"]
save_conversation_memory(session_id, final_memory)

# Return result (no more conversation_context in return dict)
return {
    "answer": ...,
    "session_id": ...,
    "candidate_ids": ...,
    "conversation_memory": final_memory  # typed object, not raw dict
}
```

**Migration path for callers:** The `query()` method should still accept `conversation_context: dict = None` for backward compat but ignore it when `conversation_memory` is loaded from DB. Print a deprecation warning if `conversation_context` is passed.

---

### Step 9: Rolling Summary Upgrade

**File:** `app/workflows/intelligent_agent.py` — summarize_old_messages at L323

Upgrade the summarizer to be **topic-aware**:

1. Instead of summarizing raw message text, summarize **by topic segments**:
   ```
   Topic 1 (turns 1-3): Searched for Python developers with 5+ years → found 12 candidates
   Topic 2 (turns 4-7): Checked GitHub profile of @torvalds → 11 repos, top langs C/OpenSCAD/C++
   Topic 3 (turns 8-9): Sent interview invite to Shubham Baghel for Senior Python Developer role
   ```

2. Store the rolling summary in `memory.summary` and update it at the end of each turn (not on-the-fly during analysis).

3. Add a `memory.get_summary_for_prompt()` method that returns:
   - The rolling summary for old topics
   - Detailed data for the current topic (full tool response / candidate list)
   - This gives the LLM a "zoomed out + zoomed in" view like ChatGPT's system prompt approach

---

### Step 10: Stale Entity Cleanup

**In `ConversationMemory.bump_turn()`:**

```python
def bump_turn(self):
    self.turn_counter += 1
    # Auto-clear references older than 10 turns
    self.entities.clear_stale(self.turn_counter, ttl=10)
    # Auto-clear tool data older than 5 turns if topic changed
    if self.raw_last_tool_response:
        tool_turn = self.current_topic.started_at_turn if self.current_topic else 0
        if self.turn_counter - tool_turn > 5:
            self.raw_last_tool_response = None
```

This prevents "ghost context" from haunting unrelated queries 20 turns later.

---

### Step 11: Backward Compatibility for Streamlit & CLI

**Streamlit** (`app/UI/streamlit_app.py`):
- Replace `st.session_state.conversation_context` with `st.session_state.conversation_memory`
- But since memory is now DB-persisted, Streamlit doesn't need to round-trip it anymore — just pass `session_id` and the agent loads memory from DB automatically
- Remove `conversation_context=st.session_state.conversation_context` from the `agent.query()` call
- The `pending_tool_action` form (L309–L375) should read from `result["conversation_memory"].pending_action` instead of `conversation_context["pending_tool_action"]`

**Interactive CLI** (`scripts/interactive_agent_test.py`):
- Remove `conversation_context = {}` and the manual round-trip
- Just pass `session_id` — memory loads from DB
- MCP field collection reads from `result["conversation_memory"].pending_action`

---

## File Change Summary

| File | Action | Scope |
|------|--------|-------|
| `app/models/conversation_memory.py` | **CREATE** | ~150 lines — Pydantic models |
| `app/db/init_db.py` | MODIFY | Add `conversation_memory` column + migration |
| `app/chat/chat_manager.py` | MODIFY | Add `save_conversation_memory()` + `load_conversation_memory()` |
| `app/workflows/intelligent_agent.py` | MODIFY | Major — AgentState, analyze_query, routing, generate_answer, execute_mcp_tool, query() |
| `app/UI/streamlit_app.py` | MODIFY | Minor — remove conversation_context round-trip, read from memory |
| `scripts/interactive_agent_test.py` | MODIFY | Minor — remove conversation_context round-trip |

---

## Verification

1. **Unit test — Memory serialization:**
   ```
   memory = ConversationMemory(session_id="test")
   memory.entities.add_candidate("id1", "Alice", 1)
   memory.start_topic("github_profile", "tool", {"username": "torvalds"})
   json_str = memory.serialize()
   restored = ConversationMemory.deserialize(json_str)
   assert restored.entities.candidates[0].name == "Alice"
   ```

2. **Integration test — Multi-turn with topic shift:**
   ```
   Turn 1: "check github profile of torvalds" → tool executes, memory.current_topic = github
   Turn 2: "how many repos?" → follow-up, answers from tool data
   Turn 3: "find Python developers with 5 years experience" → topic shift detected, github context cleared
   Turn 4: "show their education" → pronoun resolution to search results (not torvalds)
   ```

3. **Integration test — Persistence:**
   ```
   Turn 1: query(...) → get session_id
   # Simulate restart: new agent instance
   agent2 = ResumeIntelligenceAgent()
   Turn 2: agent2.query("how many repos?", session_id=session_id) → loads memory from DB, answers correctly
   ```

4. **Integration test — Stale cleanup:**
   ```
   Turns 1-3: GitHub profile flow
   Turns 4-15: Various candidate searches (12 turns)
   Turn 16: "what repos does he have?" → should NOT route to GitHub follow-up (stale, >10 turns ago)
   ```

5. **Regression test — Existing flows unchanged:**
   - Email tool with field collection still works
   - Calculator still works with follow-ups
   - Normal candidate search → Q&A flow unchanged

---

## Decisions

- **DB persistence over caller round-trip:** Memory stored in `chat_sessions` table, not passed back-and-forth. Survives restarts.
- **Topic shift = 3-layer detection:** Explicit tool switch → context type switch → LLM fallback. Avoids LLM cost for obvious cases.
- **Stale entity TTL = 10 turns:** Older entities still exist in `topic_history` but don't appear in active prompt context.
- **Pydantic over TypedDict:** Enables `.model_dump_json()`, validation, IDE support, clean serialization.
- **Rolling summary = topic-segmented:** More useful than raw message dump. "Earlier you searched for X" > "User said '...', Agent said '...'".
- **No Streamlit UI changes** for now — backend handles everything; Streamlit just stops round-tripping context.

---

## Implementation Order (Recommended)

1. Step 1 (Models) → Step 2 (DB) → Step 3 (AgentState) — Foundation
2. Step 8 (Persist in query()) — Memory now loads/saves automatically
3. Step 5 (Entity tracking) → Step 4 (Topic detection) → Step 6 (Routing fix) — Core intelligence
4. Step 7 (Answer handler) → Step 9 (Summary) → Step 10 (Cleanup) — Polish
5. Step 11 (Backward compat) — Final integration