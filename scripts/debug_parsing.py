# scripts/debug_parsing.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import sqlite3

conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

print("🔍 Debugging Parsing Status\n")
print("=" * 60)

# Check document statuses
cursor.execute("""
    SELECT status, COUNT(*) as count 
    FROM documents 
    GROUP BY status
""")
statuses = cursor.fetchall()

print("\n📊 Document Status Breakdown:")
for status, count in statuses:
    print(f"   {status}: {count}")

# Check which documents are NOT parsed
cursor.execute("""
    SELECT d.document_id, d.original_filename, d.status, d.raw_text IS NOT NULL as has_text
    FROM documents d
    LEFT JOIN parsed_resumes pr ON d.document_id = pr.document_id
    WHERE pr.resume_id IS NULL
""")

unparsed = cursor.fetchall()

print(f"\n❌ Unparsed Documents: {len(unparsed)}")
if unparsed:
    print("\nDetails:")
    for doc_id, filename, status, has_text in unparsed:  # Show first 5
        print(f"   - {filename[:40]}")
        print(f"     Status: {status}")
        print(f"     Has raw_text: {has_text}")
        print()

# Check if raw_text is missing for some
cursor.execute("""
    SELECT COUNT(*) 
    FROM documents 
    WHERE raw_text IS NULL OR raw_text = ''
""")
missing_text = cursor.fetchone()[0]

print(f"\n⚠️  Documents missing raw_text: {missing_text}")

conn.close()

print("\n" + "=" * 60)
print("💡 Analysis:")
if missing_text > 0:
    print(f"   ❌ {missing_text} documents need text extraction first")
if len(unparsed) - missing_text > 0:
    print(f"   ❌ {len(unparsed) - missing_text} documents have text but failed parsing")