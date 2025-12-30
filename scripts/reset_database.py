# scripts/reset_database.py
import sqlite3
import os
import shutil

DB_PATH = "resumes.db"

print("🗑️ Completely resetting database and ChromaDB...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# DROP all tables (so new schema is created fresh)
cursor.execute("DROP TABLE IF EXISTS parsed_resumes")
cursor.execute("DROP TABLE IF EXISTS documents")
cursor.execute("DROP TABLE IF EXISTS upload_batches")

conn.commit()
conn.close()

print("✅ All tables dropped!")

# Clear ChromaDB
chroma_path = "storage/chroma"
if os.path.exists(chroma_path):
    shutil.rmtree(chroma_path)
    print("✅ ChromaDB cleared!")

print("\n🎯 NOW RUN:")
print("   1. python app/db/init_db.py")
print("   2. python scripts/process_all_resumes.py")
