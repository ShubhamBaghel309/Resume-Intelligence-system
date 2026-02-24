# Modular MCP Architecture — Complete Teaching Guide

> From monolithic email code to a plug-and-play tool system.  
> Every concept, every decision, every line of code — explained.

---

## Table of Contents

1. [The Problem We Solved](#1-the-problem-we-solved)
2. [Key Concepts You Need to Know](#2-key-concepts-you-need-to-know)
3. [The Architecture — Bird's Eye View](#3-the-architecture--birds-eye-view)
4. [Component Deep Dives](#4-component-deep-dives)
5. [The LangGraph State Machine](#5-the-langgraph-state-machine)
6. [Bugs We Hit & Engineering Lessons](#6-bugs-we-hit--engineering-lessons)
7. [How to Add a New MCP Server (The Payoff)](#7-how-to-add-a-new-mcp-server-the-payoff)
8. [Design Patterns Used](#8-design-patterns-used)
9. [Key Takeaways for an AI Engineer](#9-key-takeaways-for-an-ai-engineer)

---

## 1. The Problem We Solved

### Before (Monolithic)

The `intelligent_agent.py` file had ~250 lines of **email-specific** code baked directly into the agent:

```python
# ❌ OLD: Hardcoded in intelligent_agent.py
class InterviewDetails(BaseModel):
    job_role: str
    company_name: str
    ...

def send_email_via_mcp_node(state):
    # 40+ lines of email field validation
    # 30+ lines of Pydantic model extraction
    # 50+ lines of MCP connection code
    # 20+ lines of email-specific error handling
    ...

async def call_mcp_email_server(...):
    # Another 50 lines of async MCP code
    ...
```

**Why this was bad:**

| Problem | Impact |
|---------|--------|
| Adding a new tool (e.g., expense tracker) = edit 300+ lines in the agent | **Fragile** |
| Email field names (`job_role`, `company_name`) were hardcoded in the agent, the UI, AND the test script | **Triple coupling** |
| Validation logic lived in the agent, not the server | **Wrong responsibility** |
| `AgentState` had `is_email_action: bool` — only works for ONE tool | **Not extensible** |

### After (Modular)

```
mcp_config.json ──→ MCPRegistry ──→ execute_mcp_tool_node ──→ MCPExecutor ──→ Any Server
     ↑                                                                            ↑
  (config)                            (generic)                              (validation)
```

To add a new MCP server: edit 1 JSON file + write 1 Python script. **Zero agent changes.**

---

## 2. Key Concepts You Need to Know

### 2.1 What is MCP? (Model Context Protocol)

MCP is Anthropic's open protocol for connecting AI models to external tools/services. Think of it like USB for AI — a standardized way to plug tools into any AI system.

**The key insight:** Instead of writing tool logic inside your agent, you write a standalone **server** that speaks a standard protocol. The agent connects to it like a client.

```
┌──────────┐     stdio (stdin/stdout)     ┌──────────────┐
│  Agent   │ ─────────────────────────── │  MCP Server  │
│ (client) │      JSON-RPC messages       │  (FastMCP)   │
└──────────┘                              └──────────────┘
```

**How MCP communication works:**
1. Agent spawns the server as a subprocess (`fastmcp run server.py`)
2. Agent sends JSON-RPC messages over **stdin**
3. Server processes the request and returns result over **stdout**
4. Connection closes

**Why stdio?** It's the simplest transport — no HTTP servers, no ports, no networking. The server is just a Python script that reads stdin and writes stdout.

### 2.2 FastMCP

FastMCP is a Python framework that makes creating MCP servers trivially easy:

```python
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool()
def my_tool(param1: str, param2: int) -> dict:
    """Tool description shown to clients."""
    return {"status": "success", "result": param1 * param2}
```

The `@mcp.tool()` decorator registers the function as a callable tool. FastMCP handles all the JSON-RPC protocol details.

### 2.3 LangGraph & State Machines

LangGraph models your agent as a **directed graph** where:
- **Nodes** = functions that transform state
- **Edges** = transitions between nodes
- **State** = a `TypedDict` that flows through the graph

```python
class AgentState(TypedDict):
    query: str
    answer: str
    tool_action: dict      # ← NEW: which MCP server to call
    tool_executed: bool     # ← NEW: did it succeed?
    conversation_context: dict  # ← persists across queries
    ...
```

**Critical LangGraph behavior:** Each node receives the full state and returns a dict of keys to update. With a plain `TypedDict` (no reducer annotations), returned keys **replace** the existing values.

### 2.4 The Registry Pattern

A **registry** is a central lookup table that maps keys to configurations. Instead of `if-else` chains:

```python
# ❌ BAD: Adding a new tool = editing code
if "email" in query:
    do_email_stuff()
elif "expense" in query:
    do_expense_stuff()  # Have to add this line for each new tool!
```

You use data-driven lookup:

```python
# ✅ GOOD: Adding a new tool = editing config
server_id = registry.match_intent(query)  # Checks keywords from config
config = registry.get_server_config(server_id)  # Returns everything needed
```

### 2.5 Separation of Concerns

The core architectural principle:

| Concern | Where it lives | NOT where it lives |
|---------|---------------|-------------------|
| "Which tool handles this query?" | `MCPRegistry` (keyword matching) | ~~Agent~~ |
| "What fields are required?" | `mcp_config.json` | ~~Agent~~ |
| "Are all required fields present?" | MCP Server (server-side validation) | ~~Agent~~ |
| "How to connect to the server?" | `MCPExecutor` (stdio transport) | ~~Agent~~ |
| "What labels to show in the UI?" | `mcp_config.json → field_examples` | ~~Streamlit hardcoded~~ |

The agent only does **orchestration**: detect intent → find candidate → extract fields → call executor → handle response.

---

## 3. The Architecture — Bird's Eye View

### File Structure

```
Resume Intelligence System/
├── MCP/
│   ├── mcp_config.json              ← Single source of truth for all servers
│   └── interview_invite_sender.py   ← MCP server (FastMCP)
│
├── app/
│   ├── mcp_infra/                   ← Infrastructure layer
│   │   ├── __init__.py
│   │   ├── registry.py              ← MCPRegistry (config reader + intent matcher)
│   │   └── executor.py              ← MCPExecutor (generic MCP client)
│   │
│   └── workflows/
│       └── intelligent_agent.py     ← LangGraph agent (generic execute_mcp_tool_node)
│
├── streamlit_app.py                 ← UI (reads field config from registry)
└── scripts/
    └── interactive_agent_test.py    ← Test CLI (reads field config from registry)
```

### Data Flow — Complete Email Journey

```
User: "send interview invite to Shubham Baghel"
 │
 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 1. analyze_query_node                                               │
│    ├── LLM analyzes query → type: "email_action"                    │
│    ├── MCPRegistry.match_intent("send interview invite to...")      │
│    │   → matches keyword "send interview" → returns "interview_email"│
│    ├── state["tool_action"] = {"server_id": "interview_email", ...} │
│    └── Extracts entity: names=["shubham baghel"]                    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. sql_filter_node                                                  │
│    ├── Detects tool_action → skips job/company/location filters      │
│    ├── Only applies NAME filter: candidate_name LIKE '%shubham%'     │
│    └── Found 1 candidate via SQL                                     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. enrich_results_node                                              │
│    └── Loads full candidate data (email, name, resume_id, etc.)      │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼  (route_after_enrich checks tool_action → "execute_mcp_tool")
                          │
┌─────────────────────────────────────────────────────────────────────┐
│ 4. execute_mcp_tool_node                                            │
│    ├── MCPRegistry.get_required_fields("interview_email")            │
│    │   → ["job_role", "company_name", "interview_datetime", ...]     │
│    ├── _extract_tool_fields(query, fields, candidate_names)          │
│    │   → {job_role: None, company_name: None, ...}   (nothing found) │
│    ├── MCPExecutor.execute(script, tool, params)                     │
│    │   → Server returns: {"status": "missing_fields",                │
│    │      "missing_fields": ["job_role", "company_name", ...]}       │
│    ├── SAVES pending_tool_action to conversation_context             │
│    │   → {server_id, collected_fields, candidates, missing_fields}   │
│    └── Builds "Please provide the following:" message                │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼  → END (answer returned to user)

User sees:
  📧 Preparing to send invitation to Shubham Baghel
  Please provide:
  1. Job Role
  2. Company Name
  3. Interview Date & Time
  4. Interview Location
  5. Interviewer Name

User fills form → "Job Role: ML Intern, Company Name: Google, ..."
 │
 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ QUERY #2 — Same flow repeats, but this time:                        │
│                                                                      │
│ analyze_query_node:                                                  │
│    ├── conversation_context has pending_tool_action                   │
│    └── Detects continuation → tool_action = {server_id: "..."}       │
│                                                                      │
│ execute_mcp_tool_node:                                               │
│    ├── _extract_tool_fields("Job Role: ML Intern, ...")              │
│    │   → REGEX fast path extracts all 5 fields instantly             │
│    ├── Merges with pending_action.collected_fields                    │
│    │   → All 5 fields now filled                                     │
│    ├── MCPExecutor.execute(script, tool, all_params)                 │
│    │   → Server validates → all present → sends email!               │
│    │   → Returns: {"status": "sent", "to": "shubham@email.com"}     │
│    └── Formats success message                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Deep Dives

### 4.1 `mcp_config.json` — The Single Source of Truth

```json
{
  "servers": {
    "interview_email": {                          // ← Server ID (lookup key)
      "name": "Interview Email Sender",           // ← Human-readable name
      "script": "MCP/interview_invite_sender.py", // ← Path to FastMCP server
      "tool_name": "send_interview_invite",       // ← @mcp.tool() function name
      "description": "Send personalized interview invitation emails",
      "trigger_keywords": [                        // ← When to activate this server
        "send interview", "send email", "send invite", "email interview",
        "invite to interview", "schedule interview", "send invitation"
      ],
      "required_fields": [                         // ← What the server needs
        "job_role", "company_name", "interview_datetime",
        "interview_location", "interviewer_name"
      ],
      "field_examples": {                          // ← UI metadata
        "job_role": {
          "label": "Job Role",
          "example": "e.g., 'Machine Learning Intern', 'Software Developer'"
        },
        ...
      },
      "needs_candidate_search": true               // ← Should agent search DB first?
    }
  }
}
```

**Why this structure?**

| Field | Who uses it | Why |
|-------|------------|-----|
| `trigger_keywords` | `MCPRegistry.match_intent()` | Determines if a user query should go to this server |
| `required_fields` | `execute_mcp_tool_node` | Knows what to extract from the query |
| `field_examples` | Streamlit form + test script | Dynamic labels/placeholders — no hardcoding |
| `needs_candidate_search` | `sql_filter_node` + routing | Some tools need a candidate (email), some don't |
| `script` | `MCPExecutor` | Knows which Python file to spawn |
| `tool_name` | `MCPExecutor` | Knows which `@mcp.tool()` function to call |

**Key insight:** This file is the **contract** between all components. The agent, the UI, and the test script all read from it. Change it once, everything updates.

---

### 4.2 `MCPRegistry` — Intent Matching & Config Lookup

**File:** `app/mcp_infra/registry.py`

```python
class MCPRegistry:
    def __init__(self):
        # Resolve path: this file → mcp_infra/ → app/ → project_root/ → MCP/
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_path = os.path.join(project_root, "MCP", "mcp_config.json")
        with open(config_path, "r") as f:
            self._config = json.load(f)
```

**Path resolution explained:**

```
__file__ = .../app/mcp_infra/registry.py
                  ↑ dirname(1) = .../app/mcp_infra/
                  ↑ dirname(2) = .../app/
                  ↑ dirname(3) = .../Resume Intelligence System/   ← project_root
                  + "MCP/mcp_config.json"
```

This is a common pattern. When you don't want to hardcode absolute paths, compute them **relative to the current file's location**.

**`match_intent()` — How intent detection works:**

```python
def match_intent(self, query: str) -> Optional[str]:
    query_lower = query.lower()
    for server_id, config in self._config["servers"].items():
        for keyword in config.get("trigger_keywords", []):
            if keyword.lower() in query_lower:
                return server_id  # First match wins
    return None
```

This is a **substring match** — not regex, not ML. Simple, fast, predictable.

```
Query: "send interview invite to Shubham"
                ↓
Checks: "send interview" in "send interview invite to shubham" → YES!
Returns: "interview_email"
```

**Why not use the LLM for intent matching?**
- LLM is **slow** (500ms+) vs substring match (~0.01ms)
- LLM can hallucinate — it might think "interview tips" = "send interview"
- Keywords are **deterministic** — same input always gives same output
- But we keep LLM as **fallback** (line 685-686 in agent) for backward compatibility

---

### 4.3 `MCPExecutor` — The Universal MCP Client

**File:** `app/mcp_infra/executor.py`

This is the component that actually talks to MCP servers. It's completely **server-agnostic** — it doesn't know or care if it's sending emails, generating reports, or anything else.

**The asyncio problem (and solution):**

MCP's Python SDK is async (`async with stdio_client(...)`). But LangGraph nodes are synchronous. We can't just call `await` from a sync function.

```python
def execute(self, script_path, tool_name, params):
    try:
        # Check: is there already an event loop running?
        asyncio.get_running_loop()
        # YES → We're inside Streamlit/Jupyter (they have their own loops)
        # Can't call asyncio.run() inside a running loop!
        # Solution: run in a separate THREAD with its own loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, self._call_tool(...))
            return future.result()
    except RuntimeError:
        # NO → We're in a regular script, safe to call directly
        return asyncio.run(self._call_tool(...))
```

**Why this matters:**

```
Scenario 1: python scripts/interactive_agent_test.py
  → No running event loop → asyncio.run() works directly ✅

Scenario 2: streamlit run streamlit_app.py
  → Streamlit has its own tornado event loop
  → asyncio.run() inside a running loop → CRASH! ❌
  → ThreadPoolExecutor creates a new thread with its own loop → Works! ✅
```

This is a **real-world pattern** you'll encounter often. Many AI frameworks have async APIs, but your calling code might be sync.

**The `_call_tool()` internals:**

```python
async def _call_tool(self, script_path, tool_name, params):
    # 1. Find the fastmcp executable
    fastmcp_cmd = shutil.which("fastmcp")  # Check PATH
    if not fastmcp_cmd:
        # Fallback: check the virtual environment directly
        venv_fastmcp = os.path.join(self._project_root, "myenv311", "Scripts", "fastmcp.exe")
        ...

    # 2. Define how to connect to the server
    server_params = StdioServerParameters(
        command=fastmcp_cmd,        # The executable
        args=["run", script_path],  # "fastmcp run MCP/interview_invite_sender.py"
        env=None                    # Inherit environment variables
    )

    # 3. Strip None values (server expects missing = not sent)
    clean_params = {k: v for k, v in params.items() if v is not None}

    # 4. Connect and call
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()  # MCP handshake
            result = await session.call_tool(tool_name, arguments=clean_params)
            # Parse JSON response
            raw_text = result.content[0].text
            return json.loads(raw_text)
```

**What happens under the hood:**

```
executor.execute("MCP/interview_invite_sender.py", "send_interview_invite", {...})
    │
    ├── Spawns subprocess: fastmcp run MCP/interview_invite_sender.py
    │   (This starts the MCP server, listening on stdin)
    │
    ├── Sends JSON-RPC message over stdin:
    │   {"jsonrpc": "2.0", "method": "tools/call",
    │    "params": {"name": "send_interview_invite",
    │               "arguments": {"job_role": "ML Intern", ...}}}
    │
    ├── Server processes request, returns over stdout:
    │   {"jsonrpc": "2.0", "result": {"content": [{"text": "{\"status\":\"sent\",...}"}]}}
    │
    └── Subprocess terminates, connection closes
```

---

### 4.4 `interview_invite_sender.py` — Server-Side Validation

**File:** `MCP/interview_invite_sender.py`
**s**
The most important architectural decision: **validation lives in the server**, not the agent.

```python
@mcp.tool()
def send_interview_invite(
    resume_id: str,
    job_role: str | None = None,        # ← Optional! Can be None
    company_name: str | None = None,
    interview_datetime: str | None = None,
    interview_location: str | None = None,
    interviewer_name: str | None = None,
    tone: str = "professional"
):
    # ============= Server-side field validation =============
    missing_fields = []
    if not job_role:
        missing_fields.append("job_role")
    if not company_name:
        missing_fields.append("company_name")
    ...

    if missing_fields:
        return {
            "status": "missing_fields",           # ← Standard protocol
            "missing_fields": missing_fields,      # ← Tells agent WHAT is missing
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }

    # All fields present → proceed with actual work
    ...
```

**Why server-side validation?**

```
OLD WAY:
  Agent validates → Agent knows email needs 5 fields
  Problem: Agent is coupled to email's business rules

NEW WAY:
  Agent sends whatever it has → Server validates → Server reports what's missing
  Agent just relays the message to the user
  Agent has ZERO knowledge of what fields email needs
```

**The Standard Response Protocol:**

Every MCP server must return a dict with a `status` key:

```python
# Success
{"status": "sent", "message": "Email sent!", "to": "shubham@email.com", ...}

# Missing fields (agent interprets this as "ask user for these")
{"status": "missing_fields", "missing_fields": ["job_role", "company_name"], "message": "..."}

# Error
{"status": "error", "message": "SMTP connection failed"}
```

The agent handles all three generically — no server-specific code.

---

### 4.5 `_extract_tool_fields()` — Smart Field Extraction

**File:** `app/workflows/intelligent_agent.py` (helper function)

This function extracts field values from the user's query. It uses a **two-tier strategy**:

#### Tier 1: Regex Fast Path

When the user replies with structured text like `"Job Role: ML Intern, Company Name: Google, ..."`, we can parse it with regex — no LLM needed.

```python
# For each field, try multiple label formats:
label_variants = [
    "job role",      # job_role → job role
    "Job Role",      # job_role → Job Role (Title Case)
    "job_role",      # raw key
]

# Regex: captures value between "Label:" and the next "Label:" or end
pattern = rf"(?i){re.escape(label)}\s*:\s*(.+?)(?:,\s*(?:\w[\w ]*:)|$)"
```

**Regex breakdown:**

```
(?i)                    → Case-insensitive
{re.escape(label)}      → "Job Role" (escaped for regex safety)
\s*:\s*                 → Colon with optional spaces
(.+?)                   → Capture value (non-greedy)
(?:,\s*(?:\w[\w ]*:)|$) → Stop at next "Something:" or end of string
```

**Example:**
```
Input:  "Job Role: ML Intern, Company Name: Google, Interview Datetime: March 15"
                   ^^^^^^^^                ^^^^^^                       ^^^^^^^^
                   captured                captured                     captured
```

If regex finds ALL fields → skip LLM entirely → **instant, free, deterministic**.

#### Tier 2: LLM Extraction (Fallback)

For freeform queries like `"send ML intern interview invite to shubham baghel"`:

```python
extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract the following fields from the user query.\n"
               "Return ONLY values that are EXPLICITLY mentioned...\n"
               f"Fields to extract:\n{fields_list}"
               f"{candidate_note}\n"         # ← "Shubham Baghel is a CANDIDATE, not a field value"
               "Return valid JSON with those exact keys."),
    ("user", "Query: {query}")
])
```

**The `candidate_note` trick:**

Without it:
```
Query: "send ML intern interview to shubham baghel"
LLM output: {"job_role": "ML intern", "interviewer_name": "shubham baghel"}  ❌ WRONG
```

With it:
```
System: "IMPORTANT: The following are CANDIDATE names... Do NOT assign them: Shubham Baghel"
LLM output: {"job_role": "ML intern", "interviewer_name": null}  ✅ CORRECT
```

#### Merge Strategy

```python
# Prefer regex (exact) over LLM (may hallucinate), fill gaps from LLM
merged = {}
for f in field_names:
    merged[f] = regex_result.get(f) or llm_result.get(f)
```

The **trust hierarchy**: regex > LLM > None.

---

### 4.6 `execute_mcp_tool_node()` — The Generic Orchestrator

This is the heart of the system. It's 100% config-driven — it works for ANY server without modification.

**The 6-step flow:**

```python
def execute_mcp_tool_node(state: AgentState) -> AgentState:

    # STEP 1: Load pending action from previous turn
    pending_action = conversation_context.get("pending_tool_action")
    #        ← This is how multi-turn field collection works

    # STEP 2: Extract fields from current query
    extracted = _extract_tool_fields(query, required_fields, candidate_names)

    # STEP 3: Merge current + pending fields
    if pending_action:
        merged_fields = {f: extracted.get(f) or collected.get(f) for f in required_fields}
    #   ← "I got job_role NOW + company_name from LAST TIME"

    # STEP 4: Resolve candidates (find email addresses)
    valid = [c for c in candidates if c.get("email")]

    # STEP 5: Call MCP server
    resp = executor.execute(script_path, tool_name, params)

    # STEP 6: Handle response
    if resp["status"] == "missing_fields":
        # Save what we have + ask for the rest
        state["conversation_context"]["pending_tool_action"] = {
            "server_id": server_id,
            "collected_fields": merged_fields,     # ← Preserved for next turn
            "candidates": candidates,              # ← Don't re-search
            "missing_fields": resp["missing_fields"]
        }
        state["answer"] = _build_ask_message(...)

    elif resp["status"] in ("sent", "success"):
        state["tool_executed"] = True
        conversation_context.pop("pending_tool_action", None)  # ← Clean up
        state["answer"] = _format_success_message(...)
```

**The `pending_tool_action` lifecycle:**

```
Turn 1: "send invite to Shubham"
  → Fields missing → SAVE pending_tool_action to conversation_context
  → Return "Please provide: Job Role, Company Name, ..."

               ┌────────────────────────────────────┐
               │  pending_tool_action = {            │
               │    server_id: "interview_email",    │
               │    collected_fields: {              │
               │      job_role: None,                │
               │      company_name: None,            │
               │      ...                            │
               │    },                               │
               │    candidates: [Shubham's data],    │
               │    missing_fields: [all 5]          │
               │  }                                   │
               └────────────────────────────────────┘
                    ↓ (passed back from agent.query() return value)
                    ↓ (test script/UI stores it)
                    ↓ (passed IN to agent.query() on next call)

Turn 2: "Job Role: ML intern, Company Name: Google, ..."
  → REGEX extracts all 5 fields
  → MERGE with pending (fills any gaps)
  → All fields present → CALL server → Success!
  → DELETE pending_tool_action (done!)
```

---

## 5. The LangGraph State Machine

### The Graph

```
                    ┌─────────────────┐
                    │  analyze_query  │ (entry point)
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
    (Q&A query)                    (normal / tool action)
              │                             │
    ┌─────────▼─────────┐         ┌────────▼────────┐
    │ fetch_context_     │         │   sql_filter    │
    │ candidates         │         └────────┬────────┘
    └─────────┬──────────┘                  │
              │                    ┌────────▼────────┐
              │                    │ llm_sql_gen     │
              │                    └────────┬────────┘
              │                             │
              │                    ┌────────▼────────┐
              │                    │ vector_search   │
              │                    └────────┬────────┘
              │                             │
              │                    ┌────────▼────────┐
              │                    │ enrich_results  │
              │                    └────────┬────────┘
              │                             │
              │                ┌────────────┴────────────┐
              │                │                         │
              │       (tool_action?)              (no tool action)
              │                │                         │
              │     ┌──────────▼──────────┐    ┌────────▼────────┐
              │     │  execute_mcp_tool   │    │ generate_answer │
              │     └──────────┬──────────┘    └────────┬────────┘
              │                │                        │
              │                ▼                        │
              │               END              ┌───────┴───────┐
              │                               (retry?)         │
              │                                │               │
              └──────────────┐         (yes)───┘          (no) │
                             │                                  │
                    ┌────────▼────────┐                        ▼
                    │ generate_answer │                        END
                    └─────────────────┘
```

### Routing Functions

**`route_after_analysis`** — Decides the first fork:

```python
def route_after_analysis(state):
    if state.get("tool_action"):
        return "sql_filter"          # Tool needs candidate data → search first
    if analysis.get("is_qa_query"):
        return "fetch_context_candidates"  # Q&A → use context
    return "sql_filter"                # Default → search
```

**`route_after_enrich`** — Decides whether to call the MCP tool:

```python
def route_after_enrich(state):
    if state.get("tool_action") and not state.get("tool_executed"):
        return "execute_mcp_tool"    # Tool pending → go execute it
    return "generate_answer"          # Normal query → generate answer
```

### Why `execute_mcp_tool` → END (not → `generate_answer`)?

Because the tool node **sets `state["answer"]` directly**. There's no need for the LLM to generate an answer — the tool's response IS the answer:

```python
# If email sent successfully:
state["answer"] = "✅ Interview Email Sender - 1 successful! ..."

# If fields missing:
state["answer"] = "📧 Preparing to send invitation to Shubham Baghel\nPlease provide: ..."
```

The `generate_answer` node would only add LLM latency and potentially rephrase the structured response badly.

### AgentState — The State That Flows

```python
class AgentState(TypedDict):
    # Original fields
    query: str                  # User's question
    query_analysis: dict        # LLM's structured analysis
    search_strategy: str        # "sql_only", "hybrid", "vector_first"
    sql_filters: dict           # Extracted SQL WHERE conditions
    candidate_ids: list         # IDs from SQL
    final_results: list         # Enriched candidate data
    answer: str                 # Final response to user
    chat_history: list          # Previous messages in session

    # NEW: Modular MCP fields
    tool_action: dict           # {server_id: "...", needs_candidate_search: True}
    tool_executed: bool         # Prevents re-execution after success
    conversation_context: dict  # Persists pending_tool_action across turns
```

**Why `tool_action: dict` instead of `is_email_action: bool`?**

`bool` only supports one tool. `dict` carries the server ID and configuration:

```python
# OLD:
state["is_email_action"] = True   # Which email? What tool? No info.

# NEW:
state["tool_action"] = {
    "server_id": "interview_email",      # Which server
    "needs_candidate_search": True       # Configuration
}
```

---

## 6. Bugs We Hit & Engineering Lessons

### Bug 1: LangChain Template Variable Collision

**Symptom:**
```
INVALID_PROMPT_INPUT: Missing variables {"job_role"}
```

**Root cause:** We put `{job_role}` inside a `ChatPromptTemplate`:
```python
json_template = '{"job_role": null, "company_name": null}'
# ChatPromptTemplate saw {job_role} and treated it as a template variable!
```

**Fix:** Don't put field names in template strings. Use a separate description instead.

**Lesson:** LangChain's `ChatPromptTemplate` uses `{...}` for variable interpolation. If you need literal curly braces, escape them with `{{...}}`. But the better fix is to **restructure your prompt** so field names aren't in the template at all.

---

### Bug 2: `conversation_context` Being Overwritten

**Symptom:** Fields from Turn 1 were lost in Turn 2. The "🔄 Merging" message never appeared.

**Root cause:** In `analyze_query_node`, line 494:
```python
# ❌ This REPLACED the entire dict, destroying pending_tool_action
state["conversation_context"] = {
    "candidate_ids": [...],
    "candidate_names": [...]
}
```

**Fix:** **Update** instead of **replace**:
```python
# ✅ This PRESERVES pending_tool_action
existing_ctx = state.get("conversation_context", {})
existing_ctx["candidate_ids"] = [...]
existing_ctx["candidate_names"] = [...]
state["conversation_context"] = existing_ctx
```

**Lesson:** When multiple nodes write to the same state key, be careful about **replace vs update** semantics. This is a **classic state management bug** that happens in React, Redux, LangGraph — any system with shared state.

**Mental model:**
```python
# Replace (dangerous):
box = {"apple": 1}                  # Throws away everything else in the box

# Update (safe):
box = state.get("box", {})
box["apple"] = 1                   # Only changes one item
state["box"] = box
```

---

### Bug 3: Candidate Name Assigned to `interviewer_name`

**Symptom:** `"send ML intern interview invite to shubham baghel"` → `interviewer_name: "shubham baghel"`

**Root cause:** The LLM saw a name in the query and the only name-type field was `interviewer_name`. From the LLM's perspective, it was a reasonable extraction.

**Fix:** Pass candidate names as context with explicit instructions:
```python
candidate_note = "IMPORTANT: The following are CANDIDATE names (the person receiving 
the action), NOT field values. Do NOT assign them to any field: Shubham Baghel"
```

**Lesson:** LLMs have no concept of your application's roles. "Shubham Baghel" is just a name to the LLM — it doesn't know he's a candidate vs an interviewer. You must **provide role context** explicitly.

This is an example of **prompt engineering for structured extraction** — you're not just asking "extract fields", you're telling the LLM what each entity in the query represents.

---

### Bug 4: Interview Location Used as SQL Filter

**Symptom:** `Interview Location: Noida` → SQL: `WHERE location LIKE '%Noida%'` → 0 results (Shubham isn't in Noida)

**Root cause:** The LLM analysis extracted "Noida" as a `location` entity. The SQL filter node applied it as a candidate location filter. But "Noida" was the **interview venue**, not where the candidate lives.

**Fix:** Skip location filters (in addition to job/company filters) when processing tool actions:
```python
# Location filter
# Skip if tool action with explicit names (location may refer to interview venue)
if filters.get("location") and not should_skip_job_filters:
    where_clauses.append("location LIKE ?")
```

**Lesson:** In a multi-purpose system, the same word can have different meanings depending on context. "Noida" in a search query = where the candidate lives. "Noida" in an email action = where the interview happens. Your **filter logic must be context-aware**.

---

### Bug 5: Raw Dict Displayed in Test Script Prompts

**Symptom:** `1. Job Role ({'label': 'Job Role', 'example': "e.g., ..."}): `

**Root cause:** `field_examples` returns `{"job_role": {"label": "...", "example": "..."}}`. The code did:
```python
example = field_examples.get(field_key, "")  # Returns the full dict!
hint = f" ({example})"                        # Prints the dict as string
```

**Fix:** Extract the nested value:
```python
meta = field_examples.get(field_key, {})
example_text = meta.get("example", "") if isinstance(meta, dict) else str(meta)
```

**Lesson:** Always check what data structure a function returns. `get_field_examples()` returns nested dicts, not strings. Type-checking with `isinstance()` makes your code defensive.

---

## 7. How to Add a New MCP Server (The Payoff)

This is the whole point of the architecture. Let's say you want to add an **Expense Report Generator**.

### Step 1: Write the server script (5 minutes)

```python
# MCP/expense_report_generator.py
from fastmcp import FastMCP

mcp = FastMCP("ExpenseReportGenerator")

@mcp.tool()
def generate_expense_report(
    employee_name: str | None = None,
    department: str | None = None,
    month: str | None = None,
    total_amount: str | None = None,
):
    """Generate an expense report for an employee."""

    # Server-side validation (same pattern)
    missing = []
    if not employee_name: missing.append("employee_name")
    if not department: missing.append("department")
    if not month: missing.append("month")
    if not total_amount: missing.append("total_amount")

    if missing:
        return {"status": "missing_fields", "missing_fields": missing,
                "message": f"Missing: {', '.join(missing)}"}

    # Do the work...
    return {"status": "success",
            "message": f"Expense report generated for {employee_name} - {department} - {month}"}
```

### Step 2: Add to config (2 minutes)

```json
{
  "servers": {
    "interview_email": { ... },
    "expense_report": {
      "name": "Expense Report Generator",
      "script": "MCP/expense_report_generator.py",
      "tool_name": "generate_expense_report",
      "description": "Generate expense reports for employees",
      "trigger_keywords": [
        "expense report", "generate expense", "create expense"
      ],
      "required_fields": ["employee_name", "department", "month", "total_amount"],
      "field_examples": {
        "employee_name": {"label": "Employee Name", "example": "e.g., 'John Doe'"},
        "department":    {"label": "Department",    "example": "e.g., 'Engineering', 'Marketing'"},
        "month":         {"label": "Month",         "example": "e.g., 'January 2026'"},
        "total_amount":  {"label": "Total Amount",  "example": "e.g., '₹15,000', '$2,500'"}
      },
      "needs_candidate_search": false
    }
  }
}
```

### Step 3: Test it

```
User: "generate expense report"
Agent: "Please provide: Employee Name, Department, Month, Total Amount"
User fills form → Agent calls server → Done!
```

**Zero changes** to `intelligent_agent.py`, `streamlit_app.py`, or `interactive_agent_test.py`.

---

## 8. Design Patterns Used

### 8.1 Strategy Pattern
Different extraction **strategies** (regex vs LLM) chosen at runtime based on what works:
```
Regex found all fields? → Use regex (fast path)
Regex partial?          → Use LLM to fill gaps
LLM failed?            → Fall back to regex-only results
```

### 8.2 Registry Pattern
Central config file acts as a lookup table. New entries = new capabilities. No code changes.

### 8.3 Chain of Responsibility
Intent detection tries 3 methods in order:
```
1. MCPRegistry keyword match
2. LLM query_type == "email_action" (backward compat)
3. conversation_context has pending_tool_action
```
First one that matches wins.

### 8.4 Adapter Pattern
`MCPExecutor` adapts the async MCP protocol to sync LangGraph nodes. Handles the asyncio event loop complexity internally.

### 8.5 Open-Closed Principle (SOLID)
The system is **open for extension** (add new servers via config) but **closed for modification** (no agent code changes needed).

### 8.6 Multi-Turn State Machine
`pending_tool_action` implements a mini state machine:
```
State 1: No pending action → User triggers tool → SAVE fields + candidates
State 2: Pending action    → User provides fields → MERGE + EXECUTE
State 3: Tool executed     → CLEAR pending action
```

---

## 9. Key Takeaways for an AI Engineer

### 1. LLMs are tools, not the whole system
The LLM does query analysis and field extraction. But intent matching uses keyword lookup (fast, deterministic). Field parsing uses regex first (free, instant). The LLM is a **fallback**, not the primary path.

### 2. State management is critical
The `conversation_context` bug (overwrite vs update) caused a multi-turn failure that was invisible in single-turn tests. Always think about **state lifecycle** — who writes, who reads, what gets preserved.

### 3. Validation belongs where the knowledge lives
The email server knows what fields it needs. The agent shouldn't. When you add a new required field to the email server, you change it in ONE place (the server + config), not three (server + agent + UI).

### 4. Config-driven > Code-driven
`mcp_config.json` is read by 4 different components (registry, agent, streamlit, test script). One file change updates all of them. This is the essence of **DRY** (Don't Repeat Yourself).

### 5. Defensive extraction prevents hallucination
Telling the LLM "Shubham Baghel is a CANDIDATE, not a field value" is a form of **grounding**. Without it, the LLM fills fields with whatever names it finds. In production AI systems, you must always constrain what the LLM CAN and CANNOT do.

### 6. Design for the second tool
The first tool (email) always works because you coded specifically for it. The architecture's value is proven when the **second tool** works with zero code changes. That's the difference between "solved one problem" and "built a platform."

### 7. Debug with the data flow in mind
Every bug we hit was a **data flow** bug:
- Template variables polluting the prompt (data flowing where it shouldn't)
- State being overwritten (data disappearing)
- Candidate names leaking into field extraction (data misclassified)
- Interview location used as SQL filter (data used in wrong context)

When debugging AI systems, trace the data end-to-end. Ask: "What data entered this function? What came out? Was anything lost or corrupted?"

---

## Summary Cheat Sheet

```
┌──────────────────────────────────────────────────────────┐
│                MODULAR MCP ARCHITECTURE                   │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  mcp_config.json ─── THE CONTRACT                        │
│  ├── trigger_keywords → MCPRegistry.match_intent()       │
│  ├── required_fields  → _extract_tool_fields()           │
│  ├── field_examples   → UI forms (Streamlit/CLI)         │
│  ├── script + tool    → MCPExecutor.execute()            │
│  └── needs_candidate  → SQL filter behavior              │
│                                                           │
│  MCPRegistry ─── READS CONFIG                            │
│  ├── match_intent(query) → server_id                     │
│  ├── get_required_fields(id) → ["field1", "field2"]      │
│  └── get_field_examples(id) → {field: {label, example}}  │
│                                                           │
│  MCPExecutor ─── CALLS SERVERS                           │
│  └── execute(script, tool, params) → {status: ...}       │
│                                                           │
│  execute_mcp_tool_node ─── ORCHESTRATES                  │
│  ├── Extract fields (regex → LLM fallback)               │
│  ├── Merge with pending fields                           │
│  ├── Call server via executor                            │
│  └── Handle response (missing → ask, success → done)     │
│                                                           │
│  MCP Server ─── VALIDATES & EXECUTES                     │
│  ├── Check required fields                               │
│  ├── Return missing_fields if incomplete                 │
│  └── Do the actual work if complete                      │
│                                                           │
│  TO ADD A NEW TOOL:                                      │
│  1. Write MCP/new_server.py                              │
│  2. Add entry to mcp_config.json                         │
│  3. Done. Zero other changes.                            │
│                                                           │
└──────────────────────────────────────────────────────────┘
```
