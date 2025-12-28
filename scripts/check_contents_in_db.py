import sqlite3
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

# Check all statuses
cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
results = cursor.fetchall()

print("📊 DOCUMENT STATUS:")
for status, count in results:
    print(f"   {status}: {count}")

# Check total
cursor.execute("SELECT COUNT(*) FROM documents")
total = cursor.fetchone()[0]
print(f"\n📦 TOTAL: {total} documents")

# Check parsed resumes
cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
parsed = cursor.fetchone()[0]
print(f"✅ PARSED: {parsed} resumes")

conn.close()