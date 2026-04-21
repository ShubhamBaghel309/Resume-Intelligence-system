import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

import pdfplumber
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.models.jd import JobDescription
from app.vectorstore.jd_embeddings import create_jd_chunks, create_jd_metadata
from app.vectorstore.jd_store import JDVectorStore

load_dotenv()

DB_PATH = "resumes.db"
DEFAULT_JD_ID = "primary_jd"


def ensure_jd_tables() -> None:
    """Create JD tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jd_documents (
            document_id TEXT PRIMARY KEY,
            jd_id TEXT,
            original_filename TEXT,
            source_path TEXT,
            raw_text TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_descriptions (
            jd_id TEXT PRIMARY KEY,
            document_id TEXT,
            job_title TEXT,
            job_level TEXT,
            department TEXT,
            location TEXT,
            role_summary TEXT,
            company_overview TEXT,
            responsibilities TEXT,
            required_skills TEXT,
            nice_to_have_skills TEXT,
            benefits TEXT,
            salary_range TEXT,
            posting_date TEXT,
            status TEXT,
            original_text TEXT,
            indexed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES jd_documents(document_id)
        )
        """
    )

    conn.commit()
    conn.close()


def load_text_from_file(path: str) -> str:
    """Read JD text from txt/md/pdf file."""
    ext = Path(path).suffix.lower()
    if ext in {".txt", ".md"}:
        return Path(path).read_text(encoding="utf-8")

    if ext == ".pdf":
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()

    raise ValueError(f"Unsupported file type: {ext}. Use .txt, .md, or .pdf")


def parse_jd_with_rules(raw_text: str, jd_id: str, fallback_title: str = "Job Description") -> JobDescription:
    """Regex/rule-based fallback parser when LLM parsing is unavailable."""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    title = fallback_title

    for ln in lines[:10]:
        if len(ln.split()) <= 12 and any(k in ln.lower() for k in ["engineer", "developer", "manager", "analyst", "scientist", "architect", "lead"]):
            title = ln
            break

    skill_pattern = re.compile(r"\b(Python|Java|JavaScript|TypeScript|React|Node|SQL|AWS|Azure|GCP|Docker|Kubernetes|TensorFlow|PyTorch|FastAPI|Django|Flask)\b", re.IGNORECASE)
    found_skills = sorted({m.group(0) for m in skill_pattern.finditer(raw_text)})

    responsibilities = []
    for ln in lines:
        if ln.startswith(("-", "*", "•")) and len(ln) > 15:
            responsibilities.append(ln.lstrip("-*• ").strip())

    role_summary = " ".join(lines[:4])[:600] if lines else ""

    return JobDescription(
        jd_id=jd_id,
        job_title=title,
        role_summary=role_summary,
        responsibilities=responsibilities[:15],
        required_skills=found_skills[:30],
        nice_to_have_skills=[],
        benefits=[],
        status="open",
        original_text=raw_text,
    )


def parse_jd_with_llm(raw_text: str, jd_id: str, fallback_title: str = "Job Description") -> JobDescription:
    """Parse JD text into structured schema using GPT-4o-mini with safe fallback."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("   [WARN] OPENAI_API_KEY not found. Using rule-based parser.")
        return parse_jd_with_rules(raw_text, jd_id, fallback_title)

    parser = PydanticOutputParser(pydantic_object=JobDescription)
    prompt = PromptTemplate(
        template="""
You are an expert recruiter assistant. Extract structured fields from the job description below.

Rules:
- Return ALL lists as arrays of strings.
- If information is missing, use null for scalar fields and [] for list fields.
- Keep skills concise and deduplicated.
- Keep responsibilities as action-oriented bullet-style lines.
- Set status as 'open' unless explicitly stated otherwise.
- Set jd_id exactly as provided.

{format_instructions}

jd_id: {jd_id}
Job Description Text:
{jd_text}

Return only valid JSON matching the schema.
""",
        input_variables=["jd_text", "jd_id"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=4096,
        openai_api_key=api_key,
    )

    chain = prompt | llm | parser

    try:
        jd = chain.invoke({"jd_text": raw_text, "jd_id": jd_id})
        jd.original_text = raw_text
        if not jd.job_title:
            jd.job_title = fallback_title
        return jd
    except Exception as err:
        print(f"   [WARN] LLM parsing failed. Falling back to rule-based parser: {err}")
        return parse_jd_with_rules(raw_text, jd_id, fallback_title)


def upsert_jd_document(jd_id: str, source_path: str, raw_text: str) -> str:
    """Store raw JD text in jd_documents table (replace mode)."""
    document_id = str(uuid.uuid4())

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM jd_documents WHERE jd_id = ?", (jd_id,))
    cur.execute(
        """
        INSERT INTO jd_documents (document_id, jd_id, original_filename, source_path, raw_text, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            jd_id,
            Path(source_path).name,
            source_path,
            raw_text,
            "parsed",
        ),
    )

    conn.commit()
    conn.close()
    return document_id


def upsert_job_description(jd: JobDescription, document_id: str) -> None:
    """Upsert parsed JD object into job_descriptions table (replace mode)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO job_descriptions (
            jd_id, document_id, job_title, job_level, department, location,
            role_summary, company_overview, responsibilities, required_skills,
            nice_to_have_skills, benefits, salary_range, posting_date, status,
            original_text, indexed_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            jd.jd_id,
            document_id,
            jd.job_title,
            jd.job_level,
            jd.department,
            jd.location,
            jd.role_summary,
            jd.company_overview,
            json.dumps(jd.responsibilities),
            json.dumps(jd.required_skills),
            json.dumps(jd.nice_to_have_skills),
            json.dumps(jd.benefits),
            json.dumps(jd.salary_range.model_dump() if jd.salary_range else {}),
            jd.posting_date,
            jd.status,
            jd.original_text,
            None,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def mark_jd_indexed(jd_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE job_descriptions SET indexed_at = ?, updated_at = ? WHERE jd_id = ?",
        (datetime.now().isoformat(), datetime.now().isoformat(), jd_id),
    )
    conn.commit()
    conn.close()


def index_jd(jd: JobDescription, document_id: str) -> None:
    """Chunk and index JD into dedicated JD vector store."""
    vector_store = JDVectorStore(persist_directory="storage/chroma_jd")
    chunks = create_jd_chunks(jd)
    metadata = create_jd_metadata(jd, document_id=document_id)

    vector_store.add_jd_chunks(
        jd_id=jd.jd_id,
        chunks=chunks,
        metadata=metadata,
    )


def run_indexing(input_path: str, jd_id: str = DEFAULT_JD_ID, title: Optional[str] = None) -> None:
    ensure_jd_tables()

    print("=" * 70)
    print("JD INDEXING PIPELINE")
    print("=" * 70)

    print("\n1) Loading JD text...")
    raw_text = load_text_from_file(input_path)
    if not raw_text.strip():
        raise ValueError("JD file appears empty after extraction.")
    print(f"   [OK] Loaded {len(raw_text)} characters")

    print("\n2) Parsing JD into structured schema...")
    fallback_title = title or Path(input_path).stem
    jd = parse_jd_with_llm(raw_text=raw_text, jd_id=jd_id, fallback_title=fallback_title)
    print(f"   [OK] Parsed JD title: {jd.job_title}")

    print("\n3) Saving raw and structured JD to DB...")
    document_id = upsert_jd_document(jd_id=jd_id, source_path=input_path, raw_text=raw_text)
    upsert_job_description(jd=jd, document_id=document_id)
    print(f"   [OK] Saved JD with jd_id={jd_id}")

    print("\n4) Indexing JD chunks to dedicated vector DB...")
    index_jd(jd=jd, document_id=document_id)
    mark_jd_indexed(jd_id=jd_id)
    print("   [OK] Indexed into storage/chroma_jd (collection: job_descriptions)")

    print("\n5) Quick verification...")
    store = JDVectorStore(persist_directory="storage/chroma_jd")
    results = store.search(query=jd.job_title, top_k=3)
    hit_count = len(results.get("ids", [[]])[0]) if results.get("ids") else 0
    print(f"   [OK] Verification search returned {hit_count} chunk(s)")

    print("\n" + "=" * 70)
    print("JD indexing completed successfully")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index a Job Description into dedicated JD vector DB.")
    parser.add_argument("--input", required=True, help="Path to JD file (.txt, .md, .pdf)")
    parser.add_argument("--jd-id", default=DEFAULT_JD_ID, help="JD identifier (default: primary_jd)")
    parser.add_argument("--title", default=None, help="Fallback title if parser cannot infer one")

    args = parser.parse_args()
    run_indexing(input_path=args.input, jd_id=args.jd_id, title=args.title)


if __name__ == "__main__":
    main()
