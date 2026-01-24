import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.ingestion.extractor import extract_text_from_pdf, save_extracted_text

DB_PATH = "resumes.db"

print("=" * 70)
print("Extracting Text from Unextracted PDFs (Incremental)")
print("=" * 70)

# Get all documents that have been uploaded but not yet extracted
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT document_id, file_path, original_filename, batch_id
    FROM documents 
    WHERE status = 'uploaded'
    AND raw_text IS NULL
    ORDER BY created_at
""")

documents = cursor.fetchall()
conn.close()

if not documents:
    print("❌ No unextracted documents found!")
    print("   All documents are already extracted.")
    exit(0)

print(f"✅ Found {len(documents)} documents to extract text from\n")

# Extract text for each document
success = 0
failed = 0
failed_files = []

for i, (document_id, file_path, filename, batch_id) in enumerate(documents, 1):
    print(f"[{i}/{len(documents)}] {filename}")
    
    try:
        text = extract_text_from_pdf(file_path)
        save_extracted_text(document_id, text)
        
        print(f"   ✅ Success! Extracted {len(text)} characters\n")
        success += 1
        
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}\n")
        failed += 1
        failed_files.append((filename, str(e)))

# Verify extraction
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT COUNT(*), 
           COUNT(CASE WHEN raw_text IS NOT NULL THEN 1 END),
           COUNT(CASE WHEN raw_text IS NULL THEN 1 END)
    FROM documents 
    WHERE status = 'uploaded'
""")

total, extracted, not_extracted = cursor.fetchone()
conn.close()

print("=" * 70)
print("✅ Text Extraction Complete!")
print("=" * 70)
print(f"   ✅ Successful: {success}")
print(f"   ❌ Failed: {failed}")
if success + failed > 0:
    print(f"   📈 Success Rate: {success/(success+failed)*100:.1f}%")

print(f"\n📊 Database Status:")
print(f"   Total Uploaded: {total}")
print(f"   Extracted: {extracted}")
print(f"   Not Extracted: {not_extracted}")

if failed_files:
    print(f"\n❌ Failed files (first 10):")
    for fname, error in failed_files[:10]:
        print(f"   - {fname}: {error}")

print("\n📌 Next step: Run 'python scripts/test_parser.py' to parse all extracted resumes!")
print("=" * 70)