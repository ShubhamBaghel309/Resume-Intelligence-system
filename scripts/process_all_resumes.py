# scripts/process_all_resumes.py
"""
Complete Resume Processing Pipeline
Uploads → Parses → Indexes all resumes in one go
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.uploader import store_uploaded_pdfs
from app.ingestion.extractor import process_batch, extract_text_from_pdf, save_extracted_text
from app.parsing.resume_parser import parse_resume_with_llm, save_parsed_resume
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume
import sqlite3
import json
from datetime import datetime
import time

# ============= CONFIGURATION =============
PDF_FOLDER = "D:/GEN AI internship work/Resume Intelligence System/resumedata/resumedata"
DB_PATH = "resumes.db"
VECTOR_STORE_PATH = "storage/chroma"

# ============= STEP 1: UPLOAD PDFs =============
def upload_pdfs():
    print("\n" + "="*70)
    print("📤 STEP 1: UPLOADING PDFs TO DATABASE")
    print("="*70)
    
    # CHECK IF ALREADY UPLOADED
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    existing_count = cursor.fetchone()[0]
    conn.close()
    
    if existing_count > 0:
        print(f"⚠️  Found {existing_count} documents already in database")
        print("ℹ️  Skipping upload to avoid duplicates")
        return "existing_batch"
    
    pdf_files = list(Path(PDF_FOLDER).glob("*.pdf"))
    print(f"📂 Found {len(pdf_files)} PDF files in {PDF_FOLDER}")
    
    if not pdf_files:
        print("❌ No PDFs found! Check the folder path.")
        return None
    
    try:
        batch_id = store_uploaded_pdfs(
            pdf_paths=pdf_files,
            recruiter_id="admin_bulk_import"
        )
        print(f"✅ Upload complete! Batch ID: {batch_id}")
        return batch_id
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


# ============= STEP 2: EXTRACT TEXT FROM PDFs =============
def extract_all_text(batch_id):
    print("\n" + "="*70)
    print("📄 STEP 2: EXTRACTING TEXT FROM PDFs")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all uploaded documents that haven't been extracted yet
    cursor.execute("""
        SELECT document_id, file_path, original_filename
        FROM documents
        WHERE batch_id = ? AND status = 'uploaded'
    """, (batch_id,))
    
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
    print("🔍 STEP 4: INDEXING TO VECTOR STORE")
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
        WHERE d.status = 'parsed'
        AND pr.indexed_at IS NULL
    """)
    
    resumes = cursor.fetchall()
    conn.close()
    
    if not resumes:
        print("ℹ️  No parsed resumes found to index.")
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
                work_experience=json.loads(resume_dict['work_experience']) if resume_dict.get('work_experience') else [],
                education=json.loads(resume_dict['education']) if resume_dict.get('education') else []
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
            
            # Update indexed_at timestamp
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