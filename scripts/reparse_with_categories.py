# scripts/reparse_with_categories.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
from app.parsing.resume_parser import parse_resume_with_llm

DB_PATH = "resumes.db"

print("="*70)
print("Re-parsing All Resumes with Categorized Skills")
print("="*70)

# Get all documents that were previously parsed
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT d.document_id, d.raw_text, pr.candidate_name
    FROM documents d
    JOIN parsed_resumes pr ON d.document_id = pr.document_id
    WHERE d.status = 'parsed'
""")

documents = cursor.fetchall()
total = len(documents)

print(f"\n📂 Found {total} resumes to re-parse...\n")

success_count = 0
fail_count = 0

for i, (doc_id, raw_text, name) in enumerate(documents, 1):
    try:
        print(f"[{i}/{total}] Re-parsing: {name}")
        
        # Parse with updated model
        parsed = parse_resume_with_llm(raw_text)
        
        # Update database with categorized skills
        cursor.execute("""
            UPDATE parsed_resumes
            SET 
                programming_languages = ?,
                frameworks = ?,
                tools = ?,
                technical_skills = ?,
                candidate_name = ?,
                email = ?,
                phone = ?,
                location = ?,
                total_experience_years = ?,
                current_role = ?,
                work_experience = ?,
                education = ?
            WHERE document_id = ?
        """, (
            json.dumps(parsed.programming_languages),
            json.dumps(parsed.frameworks),
            json.dumps(parsed.tools),
            json.dumps(parsed.technical_skills),
            parsed.candidate_name,
            parsed.email,
            parsed.phone,
            parsed.location,
            parsed.total_experience_years,
            parsed.current_role,
            json.dumps([job.model_dump() for job in parsed.work_experience]),
            json.dumps([edu.model_dump() for edu in parsed.education]),
            doc_id
        ))
        
        conn.commit()
        success_count += 1
        
        # Print extracted categories
        print(f"  ✓ Languages: {len(parsed.programming_languages)} | Frameworks: {len(parsed.frameworks)} | Tools: {len(parsed.tools)}")
        
    except Exception as e:
        fail_count += 1
        print(f"  ✗ Error: {str(e)[:100]}")

conn.close()

print(f"\n{'='*70}")
print(f"✅ Re-parsing Complete!")
print(f"{'='*70}")
print(f"Success: {success_count}/{total}")
print(f"Failed: {fail_count}/{total}")