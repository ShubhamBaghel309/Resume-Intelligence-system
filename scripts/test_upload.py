# scripts/test_upload.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.uploader import store_uploaded_pdfs
import sqlite3

# ✅ Use resumedata folder (all PDFs)
PDF_FOLDER = "resumedata/resumedata"
all_pdfs = list(Path(PDF_FOLDER).glob("*.pdf"))

print("=" * 70)
print("📤 UPLOADING RESUMES TO DATABASE (Incremental)")
print("=" * 70)
print(f"📂 Folder: {PDF_FOLDER}")
print(f"📊 Found {len(all_pdfs)} total PDFs in folder\n")

if not all_pdfs:
    print("❌ No PDFs found!")
    exit(1)

# Check which files are already uploaded
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()
cursor.execute("SELECT original_filename FROM documents")
existing_filenames = {row[0] for row in cursor.fetchall()}
conn.close()

# Filter out already-uploaded PDFs
new_pdfs = [pdf for pdf in all_pdfs if pdf.name not in existing_filenames]

if not new_pdfs:
    print(f"✅ All {len(all_pdfs)} PDFs are already uploaded!")
    print(f"   No new files to upload.")
    exit(0)

print(f"✅ Already uploaded: {len(existing_filenames)} PDFs")
print(f"🆕 New PDFs to upload: {len(new_pdfs)}\n")

for i, pdf in enumerate(new_pdfs, 1):
    print(f"  [{i}] {pdf.name}")

print(f"\n🚀 Uploading {len(new_pdfs)} new PDFs...")

batch_id = store_uploaded_pdfs(
    pdf_paths=new_pdfs,
    recruiter_id="test_recruiter"
)

print(f"\n✅ Upload Complete!")
print(f"   Batch ID: {batch_id}")
print(f"   Uploaded: {len(new_pdfs)} new PDFs")

# Verify database
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM documents")
total_count = cursor.fetchone()[0]
print(f"   Total in DB: {total_count}")

cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
status_counts = cursor.fetchall()
print(f"\n📊 Database Status:")
for status, cnt in status_counts:
    print(f"   {status}: {cnt}")

conn.close()

print("\n📌 Next step: Run 'python scripts/text_extraction.py' to extract text from uploaded PDFs!")

print("\n📌 Next: Run 'python scripts/test_parser.py' to parse them!")