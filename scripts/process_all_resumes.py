# scripts/process_all_resumes.py
"""
Complete Resume Processing Pipeline - PRODUCTION VERSION
========================================================
Processes all resumes in the PDF folder through 4 stages:
1. Upload PDFs to database
2. Extract text from PDFs
3. Parse resumes using LLM (OpenAI GPT-4o-mini)
4. Index to vector store for semantic search

Features:
- Incremental processing (skips already processed files)
- Error handling with detailed reporting
- Progress tracking and summaries
- Safe API rate limiting (10 seconds between LLM calls)

Usage:
    python scripts/process_all_resumes.py

Requirements:
    - PDFs in: resumedata/resumedata/ folder
    - OpenAI API key in .env file
    - Python dependencies from requirements.txt
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.uploader import store_uploaded_pdfs
from app.ingestion.extractor import process_batch, extract_text_from_pdf, save_extracted_text
from app.parsing.resume_parser import parse_resume_with_llm, save_parsed_resume
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume, WorkExperience, Education, Project
from app.db.init_db import init_db
import sqlite3
import json
from datetime import datetime
import time
import os

# ============= CONFIGURATION =============
PDF_FOLDER = "D:/GEN AI internship work/Resume Intelligence System/resumedata/resumedata"
DB_PATH = "resumes.db"
VECTOR_STORE_PATH = "storage/chroma"

# ============= STEP 1: UPLOAD PDFs =============
def upload_pdfs():
    print("\n" + "="*70)
    print("📤 STEP 1: UPLOADING PDFs TO DATABASE (Incremental)")
    print("="*70)
    
    # Get all PDF files in folder
    pdf_files = list(Path(PDF_FOLDER).glob("*.pdf"))
    print(f"📂 Found {len(pdf_files)} PDF files in {PDF_FOLDER}")
    
    if not pdf_files:
        print("❌ No PDFs found! Check the folder path.")
        return None
    
    # Check which files are already uploaded
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT original_filename FROM documents")
    existing_filenames = {row[0] for row in cursor.fetchall()}
    total_existing = len(existing_filenames)
    conn.close()
    
    # Filter out already-uploaded PDFs
    new_pdfs = [pdf for pdf in pdf_files if pdf.name not in existing_filenames]
    
    if not new_pdfs:
        print(f"✅ All {len(pdf_files)} PDFs already uploaded!")
        print(f"ℹ️  Skipping upload - proceeding to next step")
        return "existing_batch"
    
    print(f"✅ Already uploaded: {total_existing} PDFs")
    print(f"🆕 New PDFs to upload: {len(new_pdfs)}")
    
    try:
        batch_id = store_uploaded_pdfs(
            pdf_paths=new_pdfs,
            recruiter_id="admin_bulk_import"
        )
        print(f"✅ Upload complete! Batch ID: {batch_id}")
        print(f"   Uploaded: {len(new_pdfs)} new PDFs")
        print(f"   Total in database: {total_existing + len(new_pdfs)}")
        return batch_id
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


# ============= STEP 2: EXTRACT TEXT FROM PDFs =============
def extract_all_text(batch_id):
    print("\n" + "="*70)
    print("📄 STEP 2: EXTRACTING TEXT FROM PDFs (Incremental)")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all uploaded documents that haven't been extracted yet
    cursor.execute("""
        SELECT document_id, file_path, original_filename
        FROM documents
        WHERE status = 'uploaded'
          AND raw_text IS NULL
        ORDER BY created_at
    """)
    
    documents = cursor.fetchall()
    conn.close()
    
    if not documents:
        print("ℹ️  No documents need text extraction. All may already be extracted.")
        return 0, 0
    
    print(f"📊 Found {len(documents)} PDFs to extract text from")
    
    success_count = 0
    failed_count = 0
    failed_files = []
    
    for i, (doc_id, file_path, filename) in enumerate(documents, 1):
        print(f"\n[{i}/{len(documents)}] Extracting: {filename[:60]}...")
        
        try:
            text = extract_text_from_pdf(file_path)
            save_extracted_text(doc_id, text)
            success_count += 1
            print(f"   ✅ Success! Extracted {len(text)} characters")
        except Exception as e:
            failed_count += 1
            failed_files.append((filename, str(e)))
            print(f"   ❌ Failed: {str(e)}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 EXTRACTION SUMMARY:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    if success_count + failed_count > 0:
        print(f"   📈 Success Rate: {success_count/(success_count+failed_count)*100:.1f}%")
    
    if failed_files:
        print("\n❌ Failed files:")
        for fname, error in failed_files[:10]:  # Show first 10
            print(f"   - {fname}: {error}")
    
    return success_count, failed_count


# ============= STEP 3: PARSE RESUMES =============
def parse_all_resumes():
    print("\n" + "="*70)
    print("🧠 STEP 3: PARSING RESUMES WITH LLM")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all unparsed documents (not already parsed)
    cursor.execute("""
        SELECT d.document_id, d.raw_text, d.original_filename
        FROM documents d
        WHERE d.status = 'extracted'
        AND NOT EXISTS (
            SELECT 1 FROM parsed_resumes pr WHERE pr.document_id = d.document_id
        )
        ORDER BY d.created_at
    """)
    
    documents = cursor.fetchall()
    conn.close()
    
    if not documents:
        print("ℹ️  No unparsed documents found. All resumes may already be parsed.")
        return 0, 0
    
    print(f"📊 Found {len(documents)} documents to parse")
    print(f"⏱️  Estimated time: ~{len(documents) * 2} seconds ({len(documents) * 2 / 60:.1f} minutes)")
    
    success_count = 0
    failed_count = 0
    failed_files = []
    
    for i, (doc_id, raw_text, filename) in enumerate(documents, 1):
        print(f"\n[{i}/{len(documents)}] Parsing: {filename[:60]}...")
        
        try:
            parsed = parse_resume_with_llm(raw_text)
            save_parsed_resume(doc_id, parsed)
            
            # Update document status to 'parsed'
            update_conn = sqlite3.connect(DB_PATH)
            update_cursor = update_conn.cursor()
            update_cursor.execute(
                "UPDATE documents SET status = 'parsed' WHERE document_id = ?",
                (doc_id,)
            )
            update_conn.commit()
            update_conn.close()
            
            success_count += 1
            print(f"   ✅ Success! Total: {success_count}/{i}")
            
        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            failed_files.append((filename, error_msg))
            print(f"   ❌ Failed: {error_msg}")
            # Show detailed error for first few failures to help diagnose
            if failed_count <= 3:
                print(f"       Full error: {error_msg}")
        
        # Wait between requests to avoid rate limits
        # OpenAI Tier 1: 500 RPM, 200K TPM for gpt-4o-mini
        # When sharing API key, be more conservative: 5-10 seconds between requests
        # This ensures we don't exceed TPM limits from concurrent/recent usage
        time.sleep(10)  # 10 seconds = ~6 requests/min, very safe for shared API keys
    
    # Summary
    print("\n" + "="*70)
    print("📊 PARSING SUMMARY:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    if success_count + failed_count > 0:
        print(f"   📈 Success Rate: {success_count/(success_count+failed_count)*100:.1f}%")
    
    if failed_files:
        print("\n❌ Failed files:")
        for fname, error in failed_files[:10]:  # Show first 10
            print(f"   - {fname}: {error}")
    
    return success_count, failed_count


# ============= STEP 3: INDEX TO VECTOR STORE =============
def index_all_resumes():
    print("\n" + "="*70)
    print("🔍 STEP 4: INDEXING TO VECTOR STORE (Incremental)")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all parsed resumes that haven't been indexed yet
    cursor.execute("""
        SELECT 
            pr.*,
            d.document_id,
            d.raw_text
        FROM parsed_resumes pr
        JOIN documents d ON pr.document_id = d.document_id
        WHERE pr.indexed_at IS NULL
        ORDER BY pr.parsed_at
    """)
    
    resumes = cursor.fetchall()
    conn.close()
    
    if not resumes:
        print("ℹ️  No unindexed resumes found. All may already be indexed.")
        return 0
    
    print(f"📊 Found {len(resumes)} parsed resumes to index")
    
    # Initialize vector store
    vector_store = ResumeVectorStore(persist_directory=VECTOR_STORE_PATH)
    
    indexed_count = 0
    
    for i, row in enumerate(resumes, 1):
        resume_dict = dict(row)
        
        print(f"\n[{i}/{len(resumes)}] Indexing: {resume_dict['candidate_name']}")
        
        try:
            # Get skills from single column (all merged)
            skills_list = json.loads(resume_dict['skills']) if resume_dict.get('skills') else []
            
            # Parse work_experience, education, projects JSON
            work_exp_data = json.loads(resume_dict['work_experience']) if resume_dict.get('work_experience') else []
            education_data = json.loads(resume_dict['education']) if resume_dict.get('education') else []
            projects_data = json.loads(resume_dict['projects']) if resume_dict.get('projects') else []
            
            # Reconstruct Pydantic objects
            work_experience = [WorkExperience(**job) for job in work_exp_data]
            education = [Education(**edu) for edu in education_data]
            projects = [Project(**proj) for proj in projects_data]
            
            # Reconstruct ParsedResume object (skills go into technical_skills, others empty)
            parsed_resume = ParsedResume(
                candidate_name=resume_dict['candidate_name'],
                email=resume_dict.get('email'),
                phone=resume_dict.get('phone'),
                location=resume_dict.get('location'),
                total_experience_years=resume_dict.get('total_experience_years'),
                current_role=resume_dict.get('current_role'),
                programming_languages=[],  # Not stored separately anymore
                frameworks=[],
                tools=[],
                technical_skills=skills_list,  # All skills merged here
                work_experience=work_experience,
                education=education,
                projects=projects,
                additional_information=resume_dict.get('additional_information')
            )
            
            # Create chunks with raw text
            chunks = create_resume_chunks(
                parsed_resume=parsed_resume,
                raw_text=resume_dict.get('raw_text', '')
            )
            
            # Create metadata
            metadata = create_resume_metadata(
                parsed_resume=parsed_resume,
                document_id=resume_dict['document_id'],
                resume_id=resume_dict['resume_id']
            )
            
            # Add to vector store
            vector_store.add_resume_chunks(
                resume_id=resume_dict['resume_id'],
                chunks=chunks,
                metadata=metadata
            )
            
            # ✅ UPDATE indexed_at timestamp after successful indexing
            update_conn = sqlite3.connect(DB_PATH)
            update_cursor = update_conn.cursor()
            update_cursor.execute(
                "UPDATE parsed_resumes SET indexed_at = ? WHERE resume_id = ?",
                (datetime.now().isoformat(), resume_dict['resume_id'])
            )
            update_conn.commit()
            update_conn.close()
            
            indexed_count += 1
            print(f"   ✅ Indexed! Total: {indexed_count}/{i}")
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
    
    print("\n" + "="*70)
    print("📊 INDEXING SUMMARY:")
    print(f"   ✅ Successfully indexed: {indexed_count}")
    print(f"   📦 Total chunks: {indexed_count * 5}")
    
    return indexed_count


# ============= MAIN PIPELINE =============
def main():
    start_time = datetime.now()
    
    print("\n" + "="*70)
    print("🚀 COMPLETE RESUME PROCESSING PIPELINE")
    print("="*70)
    print(f"📅 Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 0: Initialize Database (if not exists)
    print("\n" + "="*70)
    print("💾 STEP 0: DATABASE INITIALIZATION")
    print("="*70)
    
    if not os.path.exists(DB_PATH):
        print("📊 Database not found. Creating new database...")
        init_db()
        print("✅ Database initialized successfully!")
    else:
        print("✅ Database already exists. Checking tables...")
        # Verify tables exist by running init_db (uses CREATE TABLE IF NOT EXISTS)
        init_db()
        print("✅ Database tables verified!")
    
    # Step 1: Upload
    batch_id = upload_pdfs()
    if not batch_id:
        print("\n❌ Pipeline stopped: Upload failed")
        return
    
    # Step 2: Extract Text
    extracted, extract_failed = extract_all_text(batch_id)
    if extracted == 0:
        print("\n⚠️  No text was extracted successfully")
    
    # Step 3: Parse
    success, failed = parse_all_resumes()
    if success == 0:
        print("\n⚠️  No resumes were parsed successfully")
    
    # Step 4: Index
    indexed = index_all_resumes()
    
    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*70)
    print("🎉 PIPELINE COMPLETE!")
    print("="*70)
    print(f"⏱️  Total time: {duration}")
    print(f"📊 Results:")
    print(f"   - Uploaded: {extracted + extract_failed} documents")
    print(f"   - Extracted: {extracted} successfully")
    print(f"   - Parsed: {success} successfully")
    print(f"   - Indexed: {indexed} resumes ({indexed * 5} chunks)")
    print("="*70)


if __name__ == "__main__":
    main()