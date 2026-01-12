# scripts/reset_database.py
import sqlite3
import os
import shutil

DB_PATH = "resumes.db"

print("🗑️ Deleting parsed resumes and resetting document status...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1️⃣ Delete all parsed resumes
cursor.execute("DELETE FROM message_results")
cursor.execute("DELETE FROM chat_messages")
cursor.execute("DELETE FROM chat_sessions")

# 2️⃣ Reset document status from 'parsed' → 'uploaded'
# cursor.execute("""
#     UPDATE documents
#     SET status = 'uploaded'
#     WHERE status = 'parsed'
# """)

conn.commit()
conn.close()
print("done")
# print("✅ Parsed resumes deleted")
# print("✅ Document statuses reset to 'uploaded'")

# # 3️⃣ Clear ChromaDB (optional but recommended)
# chroma_path = "storage/chroma"
# if os.path.exists(chroma_path):
#     shutil.rmtree(chroma_path)
#     print("✅ ChromaDB cleared!")

# print("\n🎯 NOW RUN: python scripts/process_all_resumes.py")
