import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.ingestion.extractor import process_batch

DB_PATH = "resumes.db"

# Get the most recent batch_id
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT batch_id, total_files, created_at 
    FROM upload_batches 
    ORDER BY created_at DESC 
    LIMIT 1
""")
batch = cursor.fetchone()

if not batch:
    print("❌ No batches found in database")
    conn.close()
    exit(1)

batch_id, total_files, created_at = batch
print(f"📦 Processing batch: {batch_id}")
print(f"   Files: {total_files}")
print(f"   Created: {created_at}\n")

conn.close()

# Process the batch (extract text from all PDFs)
print("🔄 Extracting text from PDFs...\n")
process_batch(batch_id)

# Verify extraction worked
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT document_id, original_filename, status, raw_text 
    FROM documents 
    WHERE batch_id = ?
""", (batch_id,))

documents = cursor.fetchall()
conn.close()

print(f"\n✅ Extraction complete! Verified {len(documents)} documents:\n")

for doc_id, filename, status, raw_text in documents:
    print(f"📄 {filename}")
    print(f"   Status: {status}")
    if raw_text:
        preview = raw_text[:200].replace('\n', ' ')
        print(f"   Text preview: {preview}...\n")
    else:
        print(f"   ⚠️ No text extracted\n")