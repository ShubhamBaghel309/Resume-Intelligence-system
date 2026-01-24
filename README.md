# 📄 Resume Intelligence System

A production-ready AI-powered resume analysis and intelligent search system built with LangGraph, OpenAI GPT-4o-mini, and ChromaDB. Features conversational context awareness, intelligent SQL routing, semantic search, and multi-criteria filtering.

## 🌟 Key Features

- **🤖 Intelligent Agent Workflow**: LangGraph-based agentic system with automatic strategy selection
- **💬 Conversational Context**: Multi-turn conversations with context-aware follow-ups
- **🔍 Hybrid Search**: Combines SQL filtering with semantic vector search
- **⚡ Smart Query Routing**: Automatically decides between hardcoded SQL, LLM-generated SQL, or vector search
- **📊 Advanced Filtering**: Skills, experience, education, location, projects, and more
- **🎯 Context-Aware Follow-ups**: "Out of these, who has AWS?" correctly filters from previous results
- **📈 Aggregations & Rankings**: "How many Python developers?", "Who has the most experience?"
- **🧠 Semantic Search**: "Most advanced projects", "similar to Elon Musk"
- **📋 Flexible Output**: Compact lists (10+ candidates) or detailed profiles (1-9 candidates)

---

## 📋 Table of Contents

1. [System Requirements](#-system-requirements)
2. [Installation](#-installation)
3. [Configuration](#️-configuration)
4. [Processing Resumes](#-processing-resumes)
5. [Using the Agent](#-using-the-agent)
6. [Query Examples](#-query-examples)
7. [Architecture](#️-architecture)
8. [Troubleshooting](#-troubleshooting)
9. [API Reference](#-api-reference)

---

## 💻 System Requirements

### Required
- **Python**: 3.11 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: 2GB free space for vector database

### API Keys
- **OpenAI API Key**: Required for LLM parsing and query analysis
  - Recommended: GPT-4o-mini tier (500 RPM, 200K TPM)
  - Minimum tier: Tier 1 (3 RPM, 40K TPM)

---

## 🚀 Installation

### Step 1: Clone or Extract Project

```bash
cd "D:\GEN AI internship work\Resume Intelligence System"
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv myenv311
myenv311\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3 -m venv myenv311
source myenv311/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Required packages** (from requirements.txt):
```
langchain==0.3.14
langchain-openai==0.2.14
langchain-core==0.3.28
langchain-community==0.3.14
langgraph==0.2.59
chromadb==0.5.23
pypdf==5.1.0
python-dotenv==1.0.1
streamlit==1.41.1
pandas==2.2.3
sqlite3
```

### Step 4: Verify Installation

```bash
python -c "import langchain; import langgraph; import chromadb; print('✅ All packages installed!')"
```

---

## ⚙️ Configuration

### Step 1: Create `.env` File

Create a file named `.env` in the project root directory:

```bash
# .env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to get OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key and paste into `.env`
4. **Important**: Never share or commit this file!

### Step 2: Verify Database Structure

The system uses SQLite database `resumes.db` with these tables:

```sql
-- Main tables (auto-created on first run)
- documents         # Uploaded PDFs and extracted text
- parsed_resumes    # Structured resume data
- chat_sessions     # Conversation history
- chat_messages     # Individual messages
```

### Step 3: Prepare Resume Folder

Place all resume PDFs in:
```
resumedata/
```

**Supported formats:**
- ✅ PDF files (.pdf)
- ✅ Any size (system handles large files)
- ✅ Any structure (1-page to 10+ pages)

---

## 📂 Processing Resumes

### Complete Pipeline (Recommended)

Process all resumes in one command:

```bash
python scripts/process_all_resumes.py
```

**What it does:**
1. **Upload** PDFs to database (incremental - skips existing)
2. **Extract** text using PyPDF (incremental)
3. **Parse** resumes with GPT-4o-mini (incremental, 10s delay between calls)
4. **Index** to ChromaDB vector store (incremental)

**Expected output:**
```
🚀 COMPLETE RESUME PROCESSING PIPELINE
================================================================================
📅 Started at: 2026-01-19 15:30:00

📤 STEP 1: UPLOADING PDFs TO DATABASE (Incremental)
================================================================================
📂 Found 150 PDF files in resumedata/resumedata/
✅ Already uploaded: 100 PDFs
🆕 New PDFs to upload: 50
✅ Upload complete! Batch ID: batch_abc123
   Total in database: 150

📄 STEP 2: EXTRACTING TEXT FROM PDFs (Incremental)
================================================================================
📊 Found 50 PDFs to extract text from
[1/50] Extracting: John_Doe_Resume.pdf...
   ✅ Success! Extracted 3250 characters
...
📊 EXTRACTION SUMMARY:
   ✅ Successful: 48
   ❌ Failed: 2
   📈 Success Rate: 96.0%

🧠 STEP 3: PARSING RESUMES WITH LLM
================================================================================
📊 Found 48 documents to parse
⏱️  Estimated time: ~96 seconds (1.6 minutes)
[1/48] Parsing: John_Doe_Resume.pdf...
   ✅ Success! Total: 1/1
...
📊 PARSING SUMMARY:
   ✅ Successful: 45
   ❌ Failed: 3
   📈 Success Rate: 93.8%

🔍 STEP 4: INDEXING TO VECTOR STORE (Incremental)
================================================================================
📊 Found 45 parsed resumes to index
[1/45] Indexing: John Doe
   ✅ Indexed! Total: 1/1
...
📊 INDEXING SUMMARY:
   ✅ Successfully indexed: 45
   📦 Total chunks: 225 (45 resumes × 5 chunks each)

🎉 PIPELINE COMPLETE!
================================================================================
⏱️  Total time: 0:12:35
📊 Results:
   - Uploaded: 50 documents
   - Extracted: 48 successfully
   - Parsed: 45 successfully
   - Indexed: 45 resumes (225 chunks)
================================================================================
```

### Performance Notes

**Processing Speed:**
- **Upload**: ~0.1 seconds per PDF
- **Extract**: ~0.5 seconds per PDF
- **Parse**: ~10-12 seconds per resume (includes 10s rate limit delay)
- **Index**: ~0.5 seconds per resume

**Example for 100 resumes:**
- Upload: ~10 seconds
- Extract: ~50 seconds
- Parse: ~20 minutes (with rate limiting)
- Index: ~50 seconds
- **Total**: ~22 minutes

### Incremental Processing

The system is fully incremental - you can:
- Add new PDFs to the folder anytime
- Re-run `process_all_resumes.py` - it will only process new files
- Resume processing after interruption

**Tracking columns:**
- `documents.status`: 'uploaded' → 'extracted' → 'parsed'
- `parsed_resumes.indexed_at`: NULL until indexed

---

## 🎮 Using the Agent

### Interactive Testing Tool

Launch the conversational agent:

```bash
python scripts/interactive_agent_test.py
```

**Features:**
- Real-time query testing
- Conversation history tracking
- Session persistence
- Verbose workflow output
- Database statistics

**Example session:**
```
================================================================================
INTERACTIVE RESUME INTELLIGENCE AGENT TESTER
================================================================================

Total Resumes: 681
Python Developers: 43
3+ Years Experience: 527

🔍 Your Query: find all python developers with 5+ years experience

🧠 QUERY ANALYSIS:
   Type: skill_based
   Strategy: sql_first
   ⚡ SQL Mode: Hardcoded filters

📊 EXECUTING HARDCODED SQL FILTERS...
   💡 Skill 'Python' expanded to: Python, python
   SQL: SELECT resume_id FROM parsed_resumes 
        WHERE (skills LIKE '%Python%' OR skills LIKE '%python%')
        AND total_experience_years >= 5
   ✅ Found 15 candidates via SQL

✅ FINAL ANSWER:
================================================================================
**Found 15 candidates matching your criteria:**

| # | Name | Experience | Current Role | Key Skills | Location |
|---|------|------------|--------------|------------|----------|
| 1 | Siddhartha Bhowmick | 12.0 yrs | Test Manager | Python, Selenium, Jenkins (+28 more) | Mumbai |
...

💭 Was this response satisfactory? (y/n/comment): y

🔍 Your Query: out of these, who also has AWS experience?

🧠 QUERY ANALYSIS:
   Type: skill_based
   Strategy: sql_first
   🔗 CONTEXT FILTERING: Restricting to previous 15 candidates

📊 EXECUTING HARDCODED SQL FILTERS...
   🔗 Context mode: Requiring ALL 2 skills (AND logic)
   SQL: WHERE resume_id IN (15 previous IDs) 
        AND (skills LIKE '%AWS%')
   ✅ Found 6 candidates via SQL

✅ FINAL ANSWER:
**Found 6 candidates matching your criteria:**
...
```

### Query Types

The agent automatically handles different query types:

#### 1. **Simple Searches** (Hardcoded SQL)
```
"Find Python developers"
"Candidates in Bangalore"
"IIT graduates"
"5+ years experience"
```

#### 2. **Multi-Criteria Searches** (Hardcoded SQL with ALL filters)
```
"Python developers from IIT with 5+ years in Mumbai"
"JavaScript and Machine Learning skills"
```

#### 3. **Aggregation Queries** (LLM-Generated SQL)
```
"How many Python developers are there?"
"What's the average experience of IIT graduates?"
"Total candidates with AWS"
```

#### 4. **Ranking Queries** (LLM-Generated SQL with ORDER BY)
```
"Who has the most experience?"
"Best candidate for Python role"
"Top 5 candidates"
```

#### 5. **Semantic Queries** (Vector Search)
```
"Most advanced projects"
"Unique candidates"
"Similar to Elon Musk"
"Rare skills"
```

#### 6. **Context-Aware Follow-ups**
```
# After finding Python developers:
"Out of these, who has AWS?"
"Show their education"
"Filter to 10+ years experience"
```

#### 7. **Q&A Queries** (No Search - Uses Context)
```
# After finding a specific candidate:
"Suggest 10 technical questions based on his resume"
"Why is he suitable for this role?"
"Explain his projects"
```

---

## 💡 Query Examples

### Basic Searches

**Find by skill:**
```
"Find all Python developers"
"Candidates with machine learning experience"
"JavaScript developers"
```

**Find by education:**
```
"IIT graduates"
"MBA candidates"
"Graduates from NIT"
```

**Find by experience:**
```
"Candidates with 5+ years"
"3-7 years experience"
"Entry level candidates"
```

**Find by location:**
```
"Candidates in Mumbai"
"Bangalore developers"
```

### Multi-Criteria Searches

```
"Python developers from IIT with 5+ years"
"JavaScript and React developers in Bangalore"
"Gen AI engineers with AWS experience"
"Machine Learning developers from top institutes"
```

### Aggregation Queries

```
"How many Python developers do we have?"
"What's the average experience in our database?"
"Total candidates from IIT"
```

### Ranking Queries

```
"Who has the most experience?"
"Best candidate for Python role"
"Top 5 Gen AI developers"
"Candidate with highest experience in Machine Learning"
```

### Semantic Queries

```
"Which candidate has the most advanced projects?"
"Most unique backgrounds"
"Similar to Steve Jobs"
"Innovative thinkers"
```

### Context-Aware Follow-ups

```
User: "Find all Python developers"
Agent: [Returns 43 candidates]

User: "Out of these, who has AWS?"
Agent: [Filters the 43 for AWS skill]

User: "Show their education"
Agent: [Shows education for AWS+Python candidates]

User: "Who has 10+ years?"
Agent: [Further filters to 10+ years]
```

### Q&A Queries

```
User: "Find Shubham Baghel"
Agent: [Returns Shubham's profile]

User: "Suggest 10 technical questions based on his resume"
Agent: [Analyzes resume, generates questions - NO database search]

User: "Why is he suitable for Gen AI role?"
Agent: [Explains strengths - uses context only]
```

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUERY                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│             INTELLIGENT AGENT (LangGraph)                    │
│                                                              │
│  1. Query Analysis (GPT-4o-mini)                            │
│     ├── Entity Extraction (names, skills, etc.)            │
│     ├── Query Classification (skill/education/project)     │
│     ├── Strategy Selection (sql/vector/hybrid)             │
│     └── Complexity Detection (hardcoded vs LLM SQL)        │
│                                                              │
│  2. SQL Filter Node                                         │
│     ├── Hardcoded SQL (simple queries)                     │
│     ├── Context Detection ("out of these")                 │
│     └── Skill Expansion (JS→JavaScript, Gen AI→...)        │
│                                                              │
│  3. LLM SQL Generation (complex queries)                    │
│     ├── Aggregations (COUNT, AVG)                          │
│     ├── Rankings (ORDER BY, LIMIT)                         │
│     └── Complex Logic (nested conditions)                   │
│                                                              │
│  4. Vector Search (semantic queries)                        │
│     ├── ChromaDB (cosine similarity)                       │
│     └── OpenAI Embeddings (text-embedding-ada-002)         │
│                                                              │
│  5. Result Enrichment                                       │
│     ├── Deduplication                                       │
│     ├── Full resume data fetch                             │
│     └── Matched chunks attachment                          │
│                                                              │
│  6. Answer Generation (GPT-4o-mini)                        │
│     ├── Compact List (10+ candidates)                      │
│     ├── Detailed Profiles (1-9 candidates)                 │
│     └── Aggregation Results (numbers only)                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  NATURAL LANGUAGE ANSWER                     │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

**documents** table:
```sql
- document_id (PRIMARY KEY)
- file_path
- original_filename
- raw_text (extracted PDF text)
- status ('uploaded' | 'extracted' | 'parsed')
- created_at
```

**parsed_resumes** table:
```sql
- resume_id (PRIMARY KEY)
- document_id (FOREIGN KEY)
- candidate_name
- email, phone, location
- total_experience_years
- current_role
- skills (JSON array - ALL skills merged)
- work_experience (JSON array)
- education (JSON array)
- projects (JSON array)
- additional_information
- indexed_at (timestamp when indexed to vector store)
```

**chat_sessions** & **chat_messages**:
```sql
- Stores conversation history
- Enables context-aware follow-ups
- Tracks returned candidates per message
```

### Search Strategies

**sql_only**:
- Exact field matches (name, phone, email, education)
- Returns ALL matching candidates
- No vector search

**sql_first**:
- Clear criteria with ALL results needed
- Returns ALL SQL matches (no top_k limit)
- Example: "List all Python developers"

**vector_first**:
- Semantic/subjective queries
- Uses ChromaDB cosine similarity
- Returns top 10 most relevant
- Example: "Most advanced projects"

**hybrid**:
- SQL filters first (exact criteria)
- Vector ranks top 10 from SQL results
- Example: "Python developers with interesting projects"

---

## 🔧 Troubleshooting

### Common Issues

#### 1. ModuleNotFoundError: No module named 'langgraph'

**Solution:**
```bash
# Activate virtual environment first
myenv311\Scripts\Activate.ps1

# Verify you're in the correct environment
python -c "import sys; print(sys.prefix)"

# Reinstall if needed
pip install -r requirements.txt
```

#### 2. OpenAI API Error: Rate Limit Exceeded

**Solution:**
- System uses 10-second delays between LLM calls
- If still hitting limits, increase delay in `process_all_resumes.py`:
```python
time.sleep(15)  # Increase from 10 to 15 seconds
```

#### 3. ChromaDB: Collection already exists error

**Solution:**
```bash
# Delete vector store and reindex
rm -rf storage/chroma
python scripts/process_all_resumes.py
```

#### 4. Database locked error

**Solution:**
```bash
# Close all Python processes accessing the database
# Then retry
python scripts/process_all_resumes.py
```

#### 5. PDF extraction fails for some files

**Cause:** Scanned PDFs (images, not text)

**Solution:**
- System skips scanned PDFs automatically
- Check error log in console output
- Consider OCR for scanned PDFs (not included in current version)

#### 6. Context filtering not working ("out of these")

**Verify:**
- Previous query returned candidates (check `👥 Returned X candidates`)
- Use exact phrases: "out of these", "from these", "among these"

**Debug:**
```bash
# Enable verbose mode to see context detection
python scripts/interactive_agent_test.py
# Check for: "🔗 CONTEXT FILTERING: Restricting to previous X candidates"
```

---

## 📚 API Reference

### ResumeIntelligenceAgent

Main agent class for querying resumes.

```python
from app.workflows.intelligent_agent import ResumeIntelligenceAgent

agent = ResumeIntelligenceAgent()

result = agent.query(
    user_query="Find Python developers with 5+ years",
    session_id="optional_session_id",  # For conversation continuity
    verbose=True  # Print workflow steps
)

# Returns:
{
    'answer': str,           # Natural language answer
    'session_id': str,       # Session ID for follow-ups
    'candidate_ids': list    # List of matched resume IDs
}
```

### Query Processing Functions

#### process_all_resumes.py

**upload_pdfs()**
- Uploads PDFs from `resumedata/resumedata/` folder
- Incremental (skips existing files)
- Returns: batch_id or "existing_batch"

**extract_all_text(batch_id)**
- Extracts text from uploaded PDFs
- Uses PyPDF library
- Returns: (success_count, failed_count)

**parse_all_resumes()**
- Parses resumes with GPT-4o-mini
- 10-second delay between calls
- Returns: (success_count, failed_count)

**index_all_resumes()**
- Indexes parsed resumes to ChromaDB
- Creates 5 chunks per resume
- Returns: indexed_count

---

## 📞 Support & Maintenance

### System Health Checks

**Check database status:**
```python
import sqlite3
conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

# Total documents
cursor.execute("SELECT COUNT(*) FROM documents")
print(f"Total documents: {cursor.fetchone()[0]}")

# Total parsed resumes
cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
print(f"Total parsed: {cursor.fetchone()[0]}")

# Total indexed
cursor.execute("SELECT COUNT(*) FROM parsed_resumes WHERE indexed_at IS NOT NULL")
print(f"Total indexed: {cursor.fetchone()[0]}")
```

**Check vector store:**
```python
from app.vectorstore.chroma_store import ResumeVectorStore

store = ResumeVectorStore()
print(f"Total chunks in vector store: {store.collection.count()}")
```

### Backup & Recovery

**Backup database:**
```bash
# Backup SQLite database
cp resumes.db resumes_backup_$(date +%Y%m%d).db

# Backup vector store
cp -r storage/chroma storage/chroma_backup_$(date +%Y%m%d)
```

**Restore:**
```bash
cp resumes_backup_YYYYMMDD.db resumes.db
cp -r storage/chroma_backup_YYYYMMDD storage/chroma
```

---

## 📄 License

Proprietary - Resume Intelligence System
Copyright (c) 2026

---

## 🎯 Quick Start Summary

```bash
# 1. Activate environment
myenv311\Scripts\Activate.ps1

# 2. Set up .env file with OpenAI API key
echo "OPENAI_API_KEY=sk-proj-..." > .env

# 3. Place PDFs in folder
# Put all resume PDFs in: resumedata/resumedata/

# 4. Process all resumes
python scripts/process_all_resumes.py

# 5. Start interactive agent
python scripts/interactive_agent_test.py

# 6. Query!
🔍 Your Query: find all python developers with 5+ years in bangalore
```

---

**Built with ❤️ using LangGraph, OpenAI, and ChromaDB**
