import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from app.parsing.resume_parser import parse_resume_with_llm, save_parsed_resume

DB_PATH = "resumes.db"

print("=" * 70)
print("Parsing All Unparsed Resumes")
print("=" * 70)

# Get all documents that are extracted but not yet parsed
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT d.document_id, d.original_filename, d.raw_text
    FROM documents d
    LEFT JOIN parsed_resumes p ON d.document_id = p.document_id
    WHERE d.status = 'extracted' 
      AND d.raw_text IS NOT NULL
      AND p.resume_id IS NULL
""")

documents = cursor.fetchall()
conn.close()

if not documents:
    print("❌ No unparsed documents found!")
    print("   All resumes are already parsed.")
    exit(0)

print(f"✅ Found {len(documents)} documents to parse\n")

# Parse each document
success = 0
failed = 0

for i, (document_id, filename, raw_text) in enumerate(documents, 1):
    print(f"[{i}/{len(documents)}] {filename}")
    print(f"   Text length: {len(raw_text)} characters")
    print(f"   🔄 Parsing with LLM (takes 10-30 seconds)...")
    
    try:
        parsed_resume = parse_resume_with_llm(raw_text)
        resume_id = save_parsed_resume(document_id, parsed_resume)
        
        # Count ALL skills (merged from all categories)
        total_skills = (
            len(parsed_resume.programming_languages) +
            len(parsed_resume.frameworks) +
            len(parsed_resume.tools) +
            len(parsed_resume.technical_skills)
        )
        
        print(f"   ✅ {parsed_resume.candidate_name}")
        print(f"      Total Skills: {total_skills}, Jobs: {len(parsed_resume.work_experience)}")
        if total_skills > 0:
            print(f"      Skills breakdown: Prog={len(parsed_resume.programming_languages)}, Frameworks={len(parsed_resume.frameworks)}, Tools={len(parsed_resume.tools)}, Other={len(parsed_resume.technical_skills)}")
        print(f"      Resume ID: {resume_id}\n")
        success += 1
        
    except Exception as e:
        print(f"   ❌ Failed: {e}\n")
        failed += 1

print("=" * 70)
print(f"✅ Parsing Complete!")
print(f"   Success: {success}/{len(documents)}")
print(f"   Failed: {failed}/{len(documents)}")
print("=" * 70)
print("\n📌 Next step: Run 'python scripts/index_all_resumes.py' to index them!")