"""
Comprehensive System Verification Script
Tests all components before bulk processing
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
from app.parsing.resume_parser import parse_resume_with_llm, save_parsed_resume
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume

print("="*80)
print("🔬 SYSTEM VERIFICATION - PRE-FLIGHT CHECK")
print("="*80)

# ============= TEST 1: Database Schema =============
print("\n1️⃣ CHECKING DATABASE SCHEMA...")
conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

# Check parsed_resumes table
cursor.execute("PRAGMA table_info(parsed_resumes)")
columns = cursor.fetchall()
required_columns = ['resume_id', 'document_id', 'candidate_name', 'skills', 
                   'work_experience', 'education', 'projects', 'additional_information', 
                   'indexed_at']

existing_columns = [col[1] for col in columns]
print(f"   Found columns: {', '.join(existing_columns)}")

missing = [col for col in required_columns if col not in existing_columns]
if missing:
    print(f"   ❌ MISSING COLUMNS: {missing}")
    print("   Run: python scripts/migrate_add_additional_info.py")
else:
    print(f"   ✅ All required columns present")

# Check documents table
cursor.execute("PRAGMA table_info(documents)")
doc_cols = [col[1] for col in cursor.fetchall()]
print(f"\n   Documents table: {', '.join(doc_cols)}")
if 'raw_text' in doc_cols and 'status' in doc_cols:
    print(f"   ✅ Documents table OK")
else:
    print(f"   ❌ Documents table missing columns")

conn.close()

# ============= TEST 2: Sample Resume Parsing =============
print("\n2️⃣ TESTING RESUME PARSING WITH SAMPLE DATA...")

sample_resume = """
John Doe
Email: john.doe@email.com
Phone: +1-234-567-8900
Location: San Francisco, CA

PROFESSIONAL SUMMARY
Senior Software Engineer with 8 years of experience in full-stack development.

SKILLS
Programming Languages: Python, JavaScript, Java, TypeScript
Frameworks: React, Django, FastAPI, Node.js, Express
Tools: Docker, Kubernetes, Git, AWS, PostgreSQL, MongoDB
Technical Skills: Microservices, REST APIs, GraphQL, CI/CD, Agile

WORK EXPERIENCE
Senior Software Engineer | Google | Jan 2020 - Present
- Led development of cloud-native microservices serving 10M+ users
- Architected scalable backend systems using Python and FastAPI
- Implemented CI/CD pipelines reducing deployment time by 60%

Software Engineer | Microsoft | Jun 2017 - Dec 2019
- Developed React-based dashboards for Azure monitoring
- Built REST APIs using Node.js and Express
- Collaborated with cross-functional teams in Agile environment

EDUCATION
Master of Science in Computer Science | Stanford University | 2017
Bachelor of Science in Computer Science | UC Berkeley | 2015

PROJECTS
1. Open Source Contribution - Contributed to Django framework
2. Personal Portfolio - Built using React and AWS Lambda
3. ML Model Deployment - Deployed ML models using Docker and Kubernetes

ACHIEVEMENTS
- AWS Certified Solutions Architect
- Google Cloud Professional Developer
- Winner of HackMIT 2019
- Published 2 research papers on distributed systems

LANGUAGES
English (Native), Spanish (Fluent), Mandarin (Conversational)
"""

try:
    print("   Parsing sample resume...")
    parsed = parse_resume_with_llm(sample_resume)
    
    # Verify all fields
    print(f"\n   ✅ Candidate Name: {parsed.candidate_name}")
    print(f"   ✅ Email: {parsed.email}")
    print(f"   ✅ Phone: {parsed.phone}")
    print(f"   ✅ Location: {parsed.location}")
    print(f"   ✅ Total Experience: {parsed.total_experience_years} years")
    print(f"   ✅ Current Role: {parsed.current_role}")
    
    # Check skills extraction
    total_skills = (len(parsed.programming_languages) + len(parsed.frameworks) + 
                   len(parsed.tools) + len(parsed.technical_skills))
    print(f"\n   📊 SKILLS EXTRACTED: {total_skills} total")
    print(f"      - Programming Languages: {len(parsed.programming_languages)} → {parsed.programming_languages[:3]}")
    print(f"      - Frameworks: {len(parsed.frameworks)} → {parsed.frameworks[:3]}")
    print(f"      - Tools: {len(parsed.tools)} → {parsed.tools[:3]}")
    print(f"      - Technical Skills: {len(parsed.technical_skills)} → {parsed.technical_skills[:3]}")
    
    if total_skills == 0:
        print("   ⚠️  WARNING: No skills extracted! Check prompt.")
    elif total_skills < 10:
        print("   ⚠️  WARNING: Very few skills extracted. Expected 15+")
    else:
        print("   ✅ Good skill extraction")
    
    # Check work experience
    print(f"\n   💼 WORK EXPERIENCE: {len(parsed.work_experience)} jobs")
    for job in parsed.work_experience[:2]:
        print(f"      - {job.company}: {job.role}")
    
    # Check education
    print(f"\n   🎓 EDUCATION: {len(parsed.education)} degrees")
    for edu in parsed.education:
        print(f"      - {edu.degree} from {edu.institute}")
    
    # Check projects
    print(f"\n   🚀 PROJECTS: {len(parsed.projects)} projects")
    for proj in parsed.projects[:2]:
        print(f"      - {proj.name}")
    
    # Check additional information
    print(f"\n   📋 ADDITIONAL INFO: {len(parsed.additional_information) if parsed.additional_information else 0} chars")
    if parsed.additional_information:
        print(f"      Preview: {parsed.additional_information[:100]}...")
        if any(keyword in parsed.additional_information.lower() for keyword in ['achievement', 'award', 'certificate', 'language']):
            print("   ✅ Additional information captured")
        else:
            print("   ⚠️  Additional info may be incomplete")
    else:
        print("   ⚠️  No additional information extracted")
    
except Exception as e:
    print(f"\n   ❌ PARSING FAILED: {e}")
    print("   Check your OpenAI API key and internet connection")
    sys.exit(1)

# ============= TEST 3: Database Save =============
print("\n3️⃣ TESTING DATABASE SAVE...")

try:
    # Get a test document_id
    conn = sqlite3.connect('resumes.db')
    cursor = conn.cursor()
    
    # Create a test document
    test_doc_id = "test_verification_doc_123"
    cursor.execute("""
        INSERT OR REPLACE INTO documents (document_id, batch_id, original_filename, file_path, status, raw_text)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (test_doc_id, 'test_batch', 'test.pdf', '/tmp/test.pdf', 'extracted', sample_resume))
    conn.commit()
    
    # Save parsed resume
    resume_id = save_parsed_resume(test_doc_id, parsed)
    print(f"   ✅ Saved to database with resume_id: {resume_id}")
    
    # Verify it was saved correctly
    cursor.execute("SELECT skills, additional_information FROM parsed_resumes WHERE resume_id = ?", (resume_id,))
    row = cursor.fetchone()
    
    if row:
        skills_json = row[0]
        additional_info = row[1]
        
        skills_list = json.loads(skills_json)
        print(f"   ✅ Skills in DB: {len(skills_list)} skills")
        print(f"      Sample: {skills_list[:5]}")
        
        if additional_info:
            print(f"   ✅ Additional info in DB: {len(additional_info)} chars")
        else:
            print(f"   ⚠️  Additional info not saved")
        
        # Cleanup test data
        cursor.execute("DELETE FROM parsed_resumes WHERE resume_id = ?", (resume_id,))
        cursor.execute("DELETE FROM documents WHERE document_id = ?", (test_doc_id,))
        conn.commit()
        print("   ✅ Test data cleaned up")
    else:
        print("   ❌ Failed to retrieve saved data")
    
    conn.close()
    
except Exception as e:
    print(f"   ❌ DATABASE SAVE FAILED: {e}")
    sys.exit(1)

# ============= TEST 4: Vector Store =============
print("\n4️⃣ TESTING VECTOR STORE...")

try:
    vector_store = ResumeVectorStore()
    
    # Create chunks
    chunks = create_resume_chunks(parsed, sample_resume)
    print(f"   ✅ Created {len(chunks)} chunks")
    
    # Create metadata
    metadata = create_resume_metadata(parsed, "test_doc", "test_resume")
    print(f"   ✅ Created metadata: {list(metadata.keys())}")
    
    print("   ✅ Vector store components working")
    
except Exception as e:
    print(f"   ❌ VECTOR STORE FAILED: {e}")
    print("   This may affect search functionality")

# ============= TEST 5: Check Actual Resume Count =============
print("\n5️⃣ CHECKING CURRENT DATABASE STATUS...")

conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'uploaded'")
uploaded = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'extracted'")
extracted = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'parsed'")
parsed_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
total_parsed = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM parsed_resumes WHERE indexed_at IS NOT NULL")
indexed = cursor.fetchone()[0]

print(f"   📊 Documents Status:")
print(f"      - Uploaded (need extraction): {uploaded}")
print(f"      - Extracted (need parsing): {extracted}")
print(f"      - Parsed: {parsed_count}")
print(f"\n   📊 Parsed Resumes: {total_parsed}")
print(f"   📊 Indexed Resumes: {indexed}")

if extracted > 0:
    print(f"\n   ℹ️  Ready to parse {extracted} resumes")
else:
    print(f"\n   ℹ️  No resumes pending parsing")

conn.close()

# ============= FINAL VERDICT =============
print("\n" + "="*80)
print("🎯 FINAL VERDICT:")
print("="*80)

issues = []

if missing:
    issues.append("❌ Database schema incomplete")
if total_skills < 10:
    issues.append("⚠️  Skill extraction seems weak")
if not parsed.additional_information:
    issues.append("⚠️  Additional information not being captured")

if not issues:
    print("✅ ALL SYSTEMS GO! Ready for bulk processing.")
    print("\nNext step: python scripts/process_all_resumes.py")
else:
    print("⚠️  ISSUES DETECTED:")
    for issue in issues:
        print(f"   {issue}")
    print("\nFix these before running bulk processing.")

print("="*80)
