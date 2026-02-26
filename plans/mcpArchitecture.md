# System Design: Universal MCP Architecture
## Resume Intelligence System — Technical Architecture Document

> **Audience:** Technical / Academic  
> **Purpose:** Explain the Model Context Protocol (MCP) integration architecture, its design decisions, extensibility, and scalability  
> **Date:** February 2026

---

## 1. Executive Summary

This system integrates a **Universal MCP (Model Context Protocol) Client** into a LangGraph-based AI agent. Instead of hardcoding tool logic inside the agent, each capability (email, GitHub, calculator, JD generation) lives as an **independent MCP server** — a fully isolated Python process that the agent discovers and calls at runtime using the open MCP standard.

The result: adding a new tool requires **zero changes to the agent** — only a new server file + 7 lines of config.

---

## 2. What is MCP?

MCP (Model Context Protocol) is an open standard originally developed by Anthropic (used in Claude Desktop) for connecting AI agents to external tools and data sources over a standardized protocol.

```
┌─────────────────────────────────────────────────═
│           MCP: The "USB Standard" for AI         │
├──────────────────────────────────────────────────┤
│                                                  │
│   Without MCP:                                   │
│   Agent ──hardcoded──► Tool A (custom code)      │
│   Agent ──hardcoded──► Tool B (custom code)      │
│   Agent ──hardcoded──► Tool C (custom code)      │
│                                                  │
│   With MCP:                                      │
│   Agent ──MCP Protocol──► Any Tool (plug & play) │
│                                                  │
│   Same pattern Claude Desktop uses for           │
│   Brave Search, GitHub, Filesystem, etc.         │
└──────────────────────────────────────────────────┘
```

### Key Protocol Facts
- **Transport:** stdio (stdin/stdout) — server runs as a child process
- **Wire format:** JSON-RPC 2.0
- **Discovery method:** `tools/list` — agent asks server "what can you do?"
- **Invocation method:** `tools/call` — agent sends params, gets result
- **Schema format:** JSON Schema (OpenAPI-compatible) for all tool parameters

---

## 3. High-Level Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       RESUME INTELLIGENCE SYSTEM                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────┐    ┌─────────────────────────────────────────────────┐    ║
║  │  Streamlit  │    │              LANGGRAPH AGENT                     │    ║
║  │     UI      │◄──►│  ┌──────────────────────────────────────────┐  │    ║
║  └─────────────┘    │  │           AgentState (TypedDict)          │  │    ║
║                     │  │  query │ analysis │ results │ context     │  │    ║
║  ┌─────────────┐    │  └──────────────────────────────────────────┘  │    ║
║  │  CLI Test   │    │                    │                            │    ║
║  │   Script    │◄──►│       8-Node Directed Graph (LangGraph)         │    ║
║  └─────────────┘    │                    │                            │    ║
║                     └────────────────────┼────────────────────────────┘    ║
║                                          │                                  ║
║                     ┌────────────────────▼────────────────────────────┐    ║
║                     │           MCP INFRASTRUCTURE LAYER               │    ║
║                     │  ┌────────────────┐  ┌─────────────────────┐  │    ║
║                     │  │  MCPRegistry   │  │    MCPExecutor      │  │    ║
║                     │  │ (routing +     │  │ (protocol client +  │  │    ║
║                     │  │  schema cache) │  │  subprocess mgmt)   │  │    ║
║                     │  └────────┬───────┘  └──────────┬──────────┘  │    ║
║                     └───────────┼────────────────────┼──────────────┘    ║
║                                 │     mcp_config.json │                    ║
║                     ┌───────────▼─────────────────────▼──────────────┐    ║
║                     │              MCP SERVER LAYER                   │    ║
║                     │                                                  │    ║
║                     │  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │    ║
║                     │  │ Email    │ │Calculator│ │GitHub Profile│   │    ║
║                     │  │ Server   │ │ Server   │ │   Server     │   │    ║
║                     │  │FastMCP   │ │ FastMCP  │ │   FastMCP    │   │    ║
║                     │  └──────────┘ └──────────┘ └──────────────┘   │    ║
║                     │                            ┌──────────────┐    │    ║
║                     │                            │  JD Generator│    │    ║
║                     │                            │   FastMCP    │    │    ║
║                     │                            └──────────────┘    │    ║
║                     └──────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  DATA LAYER:  SQLite DB  │  ChromaDB Vector Store  │  .env secrets  │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 4. Component Deep Dive

### 4.1 mcp_config.json — The Registry Manifest

**Location:** `MCP/mcp_config.json`  
**Purpose:** Single source of truth for tool routing. Intentionally minimal — no parameter definitions (those live on the server).

```json
{
  "servers": {
    "interview_email": {
      "name": "Interview Email Sender",
      "script": "MCP/interview_invite_sender.py",
      "trigger_keywords": ["send interview", "send email", "send invite", ...],
      "needs_candidate_search": true,      ← agent searches DB first
      "auto_fields": ["resume_id"]         ← agent fills this automatically
    },
    "calculator": {
      "script": "MCP/calculatorMCPserver.py",
      "trigger_keywords": ["calculate", "add", "multiply", ...],
      "needs_candidate_search": false      ← execute directly, no DB search
    },
    "github_profile": {
      "script": "MCP/github_profile_server.py",
      "trigger_keywords": ["github profile", "check github", ...],
      "needs_candidate_search": false
    },
    "jd_generator": {
      "script": "MCP/jd_generator_server.py",
      "trigger_keywords": ["generate jd", "job description", ...],
      "needs_candidate_search": false
    }
  }
}
```

**Why this design is powerful:**
- Parameter names, types, descriptions → NOT in config → live on the server
- Config only handles routing concerns (keywords, search requirement, auto-fill)
- Adding server = add 7 lines to this file

---

### 4.2 MCPRegistry — Intent Router + Schema Cache

**Location:** `app/mcp_infra/registry.py`

```
MCPRegistry
│
├── __init__()
│     └── loads mcp_config.json
│     └── initializes _schema_cache: dict[server_id → list[tool_schema]]
│
├── match_intent(query: str) → server_id | None
│     └── case-insensitive substring scan of trigger_keywords
│     └── O(n) where n = total keywords across all servers
│
├── discover_tools(server_id: str) → list[dict]
│     └── Check _schema_cache[server_id] (hit → return immediately)
│     └── Miss → spawn MCPExecutor.list_tools() → subprocess call
│     └── Store result in cache
│     └── Returns: [{"name", "description", "inputSchema"}]
│
├── get_tool_name(server_id) → str
│     └── discover_tools()[0]["name"]
│
├── get_required_fields(server_id) → list[str]
│     └── discover_tools() → inputSchema.properties
│     └── Remove auto_fields (e.g., resume_id — agent fills these)
│     └── Remove fields with non-None default (truly optional)
│     └── Return: fields the user must provide
│
└── get_field_examples(server_id) → dict[field → {label, example}]
      └── Parses description strings for "(e.g., ...)" patterns
      └── Used by Streamlit UI and CLI to show helpful prompts
```

**Schema caching mechanism:**
```
Turn 1: User asks "check github profile of torvalds"
  → match_intent() → "github_profile"
  → discover_tools("github_profile") → MISS → subprocess spawn
  → tools/list request → response cached
  → get_tool_name() → "check_github_profile"    (from cache)
  → get_required_fields() → ["github_username"] (from cache)

Turn 2: User asks "check github profile of guido"
  → match_intent() → "github_profile"
  → discover_tools("github_profile") → HIT → instant return
  → No subprocess overhead
```

---

### 4.3 MCPExecutor — Protocol Client

**Location:** `app/mcp_infra/executor.py`

```
MCPExecutor
│
├── _get_server_params(script_path) → StdioServerParameters
│     └── Resolves fastmcp.exe path (PATH → fallback to myenv311/Scripts/)
│     └── Returns: {command: "fastmcp.exe", args: ["run", "<abs_path>"]}
│
├── _run_async(coroutine) → result
│     └── Streamlit safety bridge:
│           if asyncio loop already running (Streamlit):
│               spawn ThreadPoolExecutor thread → asyncio.run() there
│           else (CLI/pure Python):
│               asyncio.run() directly
│
├── list_tools(script_path) → list[dict]
│     └── Calls _run_async(_list_tools_async())
│     └── Returns normalized tool schemas
│
└── execute(script_path, tool_name, params) → dict
      └── Strips None values from params
      └── Calls _run_async(_call_tool())
      └── Returns parsed dict (or {"status":"error"} on failure)
```

**The Streamlit async problem (and solution):**
```
Problem:
  Streamlit has its own event loop running.
  asyncio.run() inside a running loop → RuntimeError.

Solution:
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  Streamlit Thread (has running loop)                │
  │              │                                      │
  │              ▼                                      │
  │  _run_async detects running loop                    │
  │              │                                      │
  │              ▼                                      │
  │  ThreadPoolExecutor spawns NEW thread               │
  │  (new thread has NO event loop)                     │
  │              │                                      │
  │              ▼                                      │
  │  asyncio.run() works cleanly in new thread          │
  │              │                                      │
  │              ▼                                      │
  │  .result() blocks until done, returns to Streamlit  │
  └─────────────────────────────────────────────────────┘
```

---

### 4.4 MCP Server Design Pattern

All 4 servers follow the same FastMCP pattern:

```python
from fastmcp import FastMCP
from pydantic import Field
from typing import Annotated

mcp = FastMCP("ServerName")               # ← declare server

@mcp.tool()                               # ← declare tool
def tool_function(
    param: Annotated[                     # ← Annotated type
        str | None,
        Field(description="What this is (e.g., 'example value')")
    ] = None,
) -> dict:                                # ← always returns dict
    # server-side validation
    if not param:
        return {"status": "missing_fields", "missing_fields": ["param"]}
    
    # business logic
    result = do_something(param)
    
    # standardized return
    return {"status": "success", "message": "...", "data": result}

if __name__ == "__main__":
    mcp.run()
```

**Why `Annotated[str | None, Field(description=...)]`?**

FastMCP reads Python type annotations and generates a JSON Schema `inputSchema` automatically:

```
Python annotation                         JSON Schema output (in tools/list)
─────────────────────────────────────     ──────────────────────────────────
Annotated[                          →     "github_username": {
  str | None,                       →       "type": ["string", "null"],
  Field(                            →       "description": "GitHub username
    description="GitHub username           (e.g., 'torvalds', 'guido')",
    (e.g., 'torvalds', 'guido')")   →       "default": null
] = None                            →     }
```

MCPRegistry then reads this schema to derive required fields and examples — **no manual config needed**.

---

### 4.5 The 4 MCP Servers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MCP SERVER CATALOG                                  │
├──────────────────┬──────────────────┬──────────────────┬────────────────┤
│  interview_email │    calculator    │  github_profile  │  jd_generator  │
├──────────────────┼──────────────────┼──────────────────┼────────────────┤
│ send_interview_  │ calculate(       │ check_github_    │ generate_job_  │
│ invite(          │  operation,      │  profile(        │  description(  │
│  resume_id,      │  a,              │  github_username │  job_title,    │
│  job_role,       │  b               │ )                │  required_     │
│  company_name,   │ )                │                  │  skills,       │
│  interview_      │                  │                  │  experience_   │
│  datetime,       │                  │                  │  level,        │
│  interview_      │                  │                  │  company_name, │
│  location,       │                  │                  │  location,     │
│  interviewer_    │                  │                  │  tone          │
│  name,           │                  │                  │ )              │
│  tone            │                  │                  │                │
│ )                │                  │                  │                │
├──────────────────┼──────────────────┼──────────────────┼────────────────┤
│ SMTP via smtplib │ Pure Python math │ GitHub REST API  │ OpenAI gpt-4o  │
│ + gpt-4o-mini    │                  │ (urllib)         │ -mini          │
├──────────────────┼──────────────────┼──────────────────┼────────────────┤
│ needs_candidate  │ needs_candidate  │ needs_candidate  │ needs_candidate│
│ _search: TRUE    │ _search: FALSE   │ _search: FALSE   │ _search: FALSE │
└──────────────────┴──────────────────┴──────────────────┴────────────────┘
```

**Types of MCP servers demonstrated:**
| Type | Example | Description |
|------|---------|-------------|
| DB-integrated | Email sender | Needs candidate data from SQLite |
| Pure compute | Calculator | Stateless math, no external deps |
| Remote API | GitHub checker | Calls external REST API |
| AI-powered | JD Generator | Calls OpenAI API inside the tool |

---

## 5. End-to-End Request Flow

### 5.1 LangGraph Node Graph

```
                    ┌─────────────────┐
         query ───► │  analyze_query  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────────────┐
              │  route_after_analysis()              │
              │                                      │
    ┌─────────▼──────┐  ┌────▼──────────────────┐  ┌▼──────────────────┐
    │   sql_filter   │  │   execute_mcp_tool    │  │fetch_context_cands│
    └───────┬────────┘  │ (no-search tools:     │  └────────┬──────────┘
            │           │  calculator, github,  │           │
    ┌───────▼────────┐  │  jd_generator)        │  ┌────────▼──────────┐
    │llm_sql_gen     │  └───────────────────────┘  │  generate_answer  │
    └───────┬────────┘            END               └───────────────────┘
            │                                               END
    ┌───────▼────────┐
    │ vector_search  │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ enrich_results │
    └───────┬────────┘
            │
     route_after_enrich()
            │
   ┌────────┴────────────────────┐
   │                             │
┌──▼──────────────────┐   ┌──────▼──────────┐
│   execute_mcp_tool  │   │ generate_answer │
│ (email: needs cands)│   │                 │
└─────────────────────┘   └─────────────────┘
          END                      END
```

---

### 5.2 Scenario A: Calculator (No-Search Tool)

**Query:** `"what is 42 multiplied by 17"`

```
Step 1: analyze_query_node
  ├── LLM classifies: query_type = "skill_based" (irrelevant — overridden)
  └── MCPRegistry.match_intent("what is 42 multiplied by 17")
        → keyword "multiply" matches "calculator" server
        → tool_action = {server_id: "calculator", needs_candidate_search: false}

Step 2: route_after_analysis()
  └── tool_action exists, needs_candidate_search = false
      → "execute_mcp_tool" (SKIP entire search pipeline)
      Print: "⚡ Skipping search: tool doesn't need candidates"

Step 3: execute_mcp_tool_node
  ├── registry.get_tool_name("calculator") → "calculate"
  ├── registry.get_required_fields("calculator") → ["operation", "a", "b"]
  ├── _extract_tool_fields(query, fields) via LLM
  │     → {operation: "multiply", a: 42.0, b: 17.0}
  ├── MCPExecutor.execute("MCP/calculatorMCPserver.py", "calculate",
  │       {operation: "multiply", a: 42.0, b: 17.0})
  │
  │   [SUBPROCESS LIFECYCLE]
  │   ├── fastmcp run MCP/calculatorMCPserver.py (spawned)
  │   ├── initialize handshake
  │   ├── tools/call {"name":"calculate","arguments":{...}}
  │   ├── Python: calculate("multiply", 42.0, 17.0) → 714.0
  │   ├── Response: {"status":"success","message":"42.0 x 17.0 = 714.0","result":714}
  │   └── subprocess terminated
  │
  └── Answer rendered: "42.0 x 17.0 = 714.0"

Total node traversal: analyze → execute_mcp_tool → END  (3 nodes, 0 DB queries)
```

---

### 5.3 Scenario B: Email Sender (Needs-Candidate-Search Tool)

**Query:** `"send interview invite to Riya Sharma for ML Engineer role at Google"`

```
Step 1: analyze_query_node
  ├── LLM: query_type = "email_action", entities.names = ["Riya Sharma"]
  └── MCPRegistry.match_intent("send interview invite...")
        → keyword "send interview" matches "interview_email"
        → tool_action = {server_id: "interview_email", needs_candidate_search: true}

Step 2: route_after_analysis()
  └── tool_action.needs_candidate_search = true
      → "sql_filter" (must find candidate first)

Step 3: sql_filter_node
  └── SQL: SELECT * FROM parsed_resumes WHERE LOWER(candidate_name) LIKE '%riya sharma%'
      → resume_id: "res_abc123"

Step 4: llm_sql_generation_node + vector_search_node + enrich_results_node
  └── Final results: [{resume_id: "res_abc123", candidate_name: "Riya Sharma", email: "..."}]

Step 5: route_after_enrich()
  └── tool_action exists, tool_executed = false
      → "execute_mcp_tool"

Step 6: execute_mcp_tool_node
  ├── _extract_tool_fields() → {job_role: "ML Engineer", company_name: "Google"}
  ├── required_fields = ["job_role", "company_name", "interview_datetime",
  │                       "interview_location", "interviewer_name"]
  ├── missing: ["interview_datetime", "interview_location", "interviewer_name"]
  │
  └── → Save pending_tool_action to conversation_context
        Answer: "To send the invite, please provide:
                 - Interview Datetime (e.g., 'January 30, 2026 at 2:00 PM')
                 - Interview Location (e.g., 'Google Meet')
                 - Interviewer Name (e.g., 'Dr. Sharma')"

[Next turn: user provides missing fields]

Step 7 (next query): "January 30 at 3 PM, Google Meet, Dr. Patel"
  ├── pending_tool_action loaded → merged with new fields
  ├── All fields present → executor.execute() called
  │
  │   [SUBPROCESS + SMTP]
  │   ├── fastmcp run interview_invite_sender.py
  │   ├── tools/call {resume_id, job_role, company_name, datetime, location, interviewer}
  │   ├── DB lookup → fetch Riya's email + skills
  │   ├── gpt-4o-mini → personalized email body + subject
  │   ├── SMTP STARTTLS → email sent
  │   └── {"status": "sent", "to": "riya@...", "subject": "..."}
  │
  └── Answer: "✅ Interview invitation sent to Riya Sharma at riya@..."
```

---

### 5.4 Scenario C: GitHub Profile + Multi-Turn Follow-Ups

**Query sequence:**

```
Turn 1: "check github profile of ShubhamBaghel309"
  analyze → (no search) → execute_mcp_tool
  ├── GitHub REST API: GET /users/ShubhamBaghel309
  ├── GET /users/ShubhamBaghel309/repos
  ├── conversation_context["last_tool_response"] = {full profile data}
  └── Answer: profile card with 29 repos, top langs: Python/Jupyter/C++

Turn 2: "is there a repo named MiniGPT in his profile?"
  analyze
  └── route_after_analysis():
        last_tool_response EXISTS, tool_action = {} (no new tool triggered)
        → "generate_answer" (skip all search AND tool execution)
  generate_answer:
  ├── last_tool_response["response"]["top_repos"] contains "MiniGPT"
  ├── LLM: "Answer from stored data only"
  └── Answer: "Yes, MiniGPT exists at github.com/ShubhamBaghel309/MiniGPT"

Turn 3: "what languages does he use?"
  → Same routing: generate_answer from stored data
  → Answer: "Python, Jupyter Notebook, C++, C"

Turn N (topic shift): "find me Python developers with 5+ years"
  analyze → tool_action = {} (no keyword match)
  → route to sql_filter (normal search)
  → GitHub context is replaced by new search results
```

---

## 6. MCP Protocol Deep Dive

### 6.1 Full JSON-RPC Message Sequence

```
┌──────────────────────────────────────────────────────────────────────┐
│                   MCP STDIO PROTOCOL FLOW                            │
│           (one connection per tool operation)                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  AGENT PROCESS              │        MCP SERVER PROCESS             │
│  (Python, port-agnostic)    │   (spawned via fastmcp run server.py) │
│                             │                                        │
│  1. SPAWN SUBPROCESS        │                                        │
│  os.Popen(["fastmcp","run", │                                        │
│  "server.py"])              │  FastMCP starts, listens on stdin     │
│                             │                                        │
│  2. HANDSHAKE               │                                        │
│  ─────────────────────────►│                                        │
│  {"jsonrpc":"2.0","id":0,   │                                        │
│   "method":"initialize",    │                                        │
│   "params":{                │                                        │
│     "protocolVersion":"x",  │                                        │
│     "capabilities":{},      │                                        │
│     "clientInfo":{}         │                                        │
│   }}                        │                                        │
│                             │ ◄──────────────────────────────────── │
│                             │  {"result":{"protocolVersion":"x",    │
│                             │    "capabilities":{"tools":{}},       │
│                             │    "serverInfo":{"name":"CalcMCP"}}}  │
│                             │                                        │
│  3. SCHEMA DISCOVERY        │                                        │
│  ─────────────────────────►│                                        │
│  {"id":1,                   │                                        │
│   "method":"tools/list",    │                                        │
│   "params":{}}              │                                        │
│                             │ ◄──────────────────────────────────── │
│                             │  {"result":{"tools":[{                 │
│                             │    "name":"calculate",                 │
│                             │    "description":"...",                │
│                             │    "inputSchema":{                     │
│                             │      "type":"object",                  │
│                             │      "properties":{                    │
│                             │        "operation":{                   │
│                             │          "type":["string","null"],     │
│                             │          "description":"add/sub/...",  │
│                             │          "default":null},              │
│                             │        "a":{"type":["number","null"]}, │
│                             │        "b":{"type":["number","null"]}  │
│                             │      }                                 │
│                             │    }]}}                                │
│                             │                                        │
│  4. TOOL INVOCATION         │                                        │
│  ─────────────────────────►│                                        │
│  {"id":2,                   │                                        │
│   "method":"tools/call",    │                                        │
│   "params":{                │                                        │
│     "name":"calculate",     │  Python executes:                     │
│     "arguments":{           │  calculate("multiply", 42.0, 17.0)   │
│       "operation":"multiply"│                                        │
│       "a":42.0,             │                                        │
│       "b":17.0              │                                        │
│     }}}                     │                                        │
│                             │ ◄──────────────────────────────────── │
│                             │  {"result":{"content":[{               │
│                             │    "type":"text",                      │
│                             │    "text":"{\"status\":\"success\",    │
│                             │     \"message\":\"42.0 x 17.0=714.0\",│
│                             │     \"result\":714.0}"}]}}             │
│                             │                                        │
│  5. SUBPROCESS TERMINATED   │                                        │
│  (context manager exit)     │  process exits cleanly                │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Double-Parse Requirement

A critical implementation detail: FastMCP wraps return values in a content wrapper. The executor must decode twice:

```
Outer envelope (JSON-RPC):
  {"result": {"content": [{"type": "text", "text": "..."}]}}
                                                   ▲
                                            This is a JSON string
                                            (not an object yet!)

Inner payload (tool result):
  json.loads(result.content[0].text)
  → {"status": "success", "message": "42.0 x 17.0 = 714.0", "result": 714.0}
```

---

## 7. Schema-Driven Auto-Discovery: The Universal Advantage

This is the key architectural innovation that makes the system scalable:

```
┌─────────────────────────────────────────────────────────────────────┐
│               HOW THE AGENT DISCOVERS A NEW TOOL                    │
│                    (Zero agent code changes)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  NEW SERVER FILE: MCP/stock_price_server.py                         │
│  ─────────────────────────────────────────                          │
│  @mcp.tool()                                                         │
│  def get_stock_price(                                               │
│      ticker: Annotated[str, Field(                                  │
│          description="Stock ticker (e.g., 'AAPL', 'GOOGL')"        │
│      )]                                                             │
│  ) -> dict: ...                                                     │
│                                                                      │
│  NEW CONFIG ENTRY: mcp_config.json (7 lines)                        │
│  ──────────────────────────────────────────                         │
│  "stock_price": {                                                    │
│    "name": "Stock Price Checker",                                   │
│    "script": "MCP/stock_price_server.py",                           │
│    "trigger_keywords": ["stock price", "share price", "ticker"],    │
│    "needs_candidate_search": false,                                  │
│    "auto_fields": []                                                 │
│  }                                                                   │
│                                                                      │
│  WHAT HAPPENS AUTOMATICALLY (no agent changes):                     │
│  ───────────────────────────────────────────────                    │
│  1. MCPRegistry.match_intent() picks up new keywords immediately    │
│  2. discover_tools() connects to new server, gets schema            │
│  3. get_required_fields() derives ["ticker"] from inputSchema       │
│  4. get_field_examples() extracts "e.g., 'AAPL'" from description   │
│  5. Agent asks user for ticker, executes tool, returns result       │
│  6. Streamlit UI auto-renders input fields for ticker               │
│  7. Follow-up questions ("what was yesterday's price?") work        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Comparison: Before vs. After Universal Architecture**

| Concern | Before (hardcoded) | After (universal MCP) |
|---------|-------------------|----------------------|
| Add a new tool | Edit agent code, add tool class, register manually | Create server file + 7-line config |
| Tool parameters | Hardcoded in agent | Auto-discovered from live server schema |
| Field validation | Agent-side checks | Server-side (standardized response format) |
| Tool description | In agent code | In server's `Field(description=...)` |
| Schema drift | Manual sync required | Impossible — always live from server |
| Testing a tool | Requires full agent | `fastmcp run server.py` then curl-style test |

---

## 8. Scalability Analysis

### 8.1 Horizontal Tool Scaling

```
Current (4 servers):              Future (N servers):
─────────────────────             ────────────────────
interview_email                   interview_email
calculator                        calculator
github_profile          ──►       github_profile
jd_generator                      jd_generator
                                  linkedin_scraper   ← new
                                  calendar_booking   ← new
                                  resume_scorer      ← new
                                  slack_notifier     ← new

Agent code changes needed: ZERO
Config changes needed: +7 lines per server
Server code needed: 1 Python file per server
```

### 8.2 Why keyword matching is fast enough

```
Current: 4 servers × ~6 keywords = 24 substring checks per query
100 servers × 6 keywords = 600 substring checks per query
                         = ~0.001ms on modern CPU (negligible)

Alternative (LLM routing): ~200-500ms per query (LLM latency)
→ Keyword matching is 1000x faster for routing
→ LLM is used as fallback only (when keyword fails)
```

### 8.3 Schema Cache Performance

```
Without cache:
  Every tool call = subprocess spawn + initialize + list_tools
  Cost: ~300-500ms per call

With _schema_cache:
  First call per server per session: ~300-500ms (subprocess spawn)
  All subsequent calls: ~0ms (dict lookup)

In a 20-turn conversation using GitHub profile 5 times:
  Without cache: 5 × 400ms = 2000ms overhead
  With cache:    1 × 400ms + 4 × 0ms = 400ms overhead
  Savings: 1600ms (75% reduction)
```

### 8.4 Isolation and Fault Tolerance

```
Traditional monolith:             MCP subprocess isolation:
─────────────────────             ─────────────────────────
┌──────────────────────┐          ┌──────────────────────┐
│  Agent Process       │          │  Agent Process       │
│  ├── Email logic     │          │  ├── MCPExecutor     │
│  ├── Calculator      │          │  └── (stable)        │
│  ├── GitHub API      │          └──────────────────────┘
│  └── JD Generator    │                    │
│                      │          spawns on demand:
│  Bug in GitHub API   │          ┌──────────────────────┐
│  crashes entire      │          │  GitHub Server       │
│  agent!              │          │  Bug crashes only    │
└──────────────────────┘          │  this subprocess     │
                                  │  Agent catches error │
                                  │  Returns graceful    │
                                  │  {"status":"error"}  │
                                  └──────────────────────┘
```

### 8.5 Remote Server Extension Path

The same MCPExecutor can connect to remote HTTP/SSE MCP servers (Claude Desktop style) with one config change:

```json
"remote_calendar": {
  "type": "http",
  "url": "https://calendar-mcp.company.com/sse",
  "auth_header": "Bearer ${CALENDAR_API_TOKEN}",
  "trigger_keywords": ["book meeting", "schedule call"],
  "needs_candidate_search": false
}
```

No agent changes — only MCPExecutor.`_get_server_params()` needs a conditional for HTTP vs stdio transport.

---

## 9. Security Design

```
┌──────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Layer 1: Subprocess Isolation                                    │
│  → Each MCP server process is sandboxed in its own subprocess   │
│  → Crash in one server cannot affect the agent process           │
│                                                                   │
│  Layer 2: None-stripping                                         │
│  → MCPExecutor strips None params before sending                 │
│  → Prevents accidental null injection to external APIs           │
│                                                                   │
│  Layer 3: Server-side field validation                           │
│  → Each server validates its own inputs                          │
│  → Returns {status: "missing_fields"} not exceptions             │
│                                                                   │
│  Layer 4: .env secret management                                 │
│  → SMTP credentials, OpenAI API key, GitHub token               │
│  → Never in config or code, only in .env                         │
│                                                                   │
│  Layer 5: Rate limit awareness                                   │
│  → GitHub: 60 req/hr (no auth) / 5000 req/hr (with token)       │
│  → OpenAI: model-level rate limits                               │
│  → SMTP: per-session connection with STARTTLS                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 10. Comparison with Claude Desktop MCP

```
┌────────────────────────┬──────────────────────┬──────────────────────┐
│ Feature                │ Claude Desktop       │ This System          │
├────────────────────────┼──────────────────────┼──────────────────────┤
│ Protocol standard      │ MCP (Anthropic)      │ MCP (same standard)  │
│ Transport              │ stdio + HTTP/SSE     │ stdio (+ HTTP ready) │
│ Schema discovery       │ tools/list           │ tools/list (same)    │
│ Tool invocation        │ tools/call           │ tools/call (same)    │
│ Server framework       │ Any MCP-compatible   │ FastMCP              │
│ Config format          │ claude_desktop.json  │ mcp_config.json      │
│ Tool routing           │ LLM decides          │ Keywords + LLM hybrid│
│ Candidate search       │ N/A                  │ Pre-tool SQL + vector│
│ Multi-turn field coll. │ Partial              │ Full pending_action  │
│ Follow-up Q&A on tools │ Context window only  │ Stored + enriched    │
│ Schema caching         │ Per session          │ Per instance         │
└────────────────────────┴──────────────────────┴──────────────────────┘
```

---

## 11. File Structure Summary

```
Resume Intelligence System/
│
├── MCP/                              ← Tool servers (each independently runnable)
│   ├── mcp_config.json               ← Routing manifest (minimal, no params)
│   ├── interview_invite_sender.py    ← SMTP + GPT email tool
│   ├── calculatorMCPserver.py        ← Pure compute tool
│   ├── github_profile_server.py      ← Remote API tool
│   └── jd_generator_server.py        ← AI generation tool
│
├── app/
│   ├── mcp_infra/                    ← Universal MCP client layer
│   │   ├── executor.py               ← Protocol client (subprocess mgmt, JSON-RPC)
│   │   └── registry.py               ← Intent router + schema cache
│   │
│   └── workflows/
│       └── intelligent_agent.py      ← LangGraph agent (8 nodes)
│           ├── analyze_query_node    ← query understanding + tool intent detection
│           ├── sql_filter_node       ← SQL candidate search
│           ├── llm_sql_generation_node
│           ├── vector_search_node    ← ChromaDB semantic search
│           ├── enrich_results_node
│           ├── fetch_context_candidates_node
│           ├── execute_mcp_tool_node ← Universal tool executor
│           └── generate_answer_node  ← Answer synthesis + follow-up handler
│
└── plans/
    ├── contextImprovement.md         ← Planned: ConversationMemory upgrade
    └── mcp_architecture.md           ← This document
```

---

## 12. Key Design Decisions & Justification

| Decision | Chosen Approach | Why |
|----------|----------------|-----|
| Protocol | MCP (open standard) | Same as Claude Desktop; vendor-neutral; future-proof |
| Server framework | FastMCP | Auto-generates JSON Schema from Python types; minimal boilerplate |
| Transport | stdio subprocess | Zero network config; process isolation; works offline |
| Routing | Keywords first, LLM fallback | 1000x faster than LLM-only; LLM handles edge cases |
| Schema discovery | Live `tools/list` on demand | No drift; adding tools needs zero config changes for params |
| Schema caching | Per-instance dict | Balance between freshness and performance |
| Field collection | Multi-turn pending_action | Natural conversation; user provides one field at a time |
| Follow-up context | `last_tool_response` in context | No re-query; instant answers about prior tool results |
| Async bridge | ThreadPoolExecutor for Streamlit | Streamlit's event loop conflict resolved cleanly |
| Server isolation | subprocess per call | Fault isolation; server bugs don't crash agent |