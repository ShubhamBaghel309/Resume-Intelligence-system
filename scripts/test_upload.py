# scripts/test_upload.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.uploader import store_uploaded_pdfs
import sqlite3

# ✅ Use resumedata folder (19 PDFs)
PDF_FOLDER = "resumedata/resumedata"
sample_pdfs = list(Path(PDF_FOLDER).glob("*.pdf"))

print("=" * 70)
print("📤 UPLOADING RESUMES TO DATABASE")
print("=" * 70)
print(f"📂 Folder: {PDF_FOLDER}")
print(f"📊 Found {len(sample_pdfs)} PDFs\n")

if not sample_pdfs:
    print("❌ No PDFs found!")
    exit(1)

for i, pdf in enumerate(sample_pdfs, 1):
    print(f"  [{i}] {pdf.name}")

print(f"\n🚀 Uploading...")

batch_id = store_uploaded_pdfs(
    pdf_paths=sample_pdfs,
    recruiter_id="test_recruiter"
)

print(f"\n✅ Upload Complete!")
print(f"   Batch ID: {batch_id}")

# Verify database
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id = ?", (batch_id,))
count = cursor.fetchone()[0]
print(f"   Documents in DB: {count}")

cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
status_counts = cursor.fetchall()
print(f"\n📊 Database Status:")
for status, cnt in status_counts:
    print(f"   {status}: {cnt}")

conn.close()

print("\n📌 Next: Run 'python scripts/test_parser.py' to parse them!")