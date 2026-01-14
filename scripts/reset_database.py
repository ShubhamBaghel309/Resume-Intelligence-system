# scripts/reset_database.py
"""
Complete Database Reset Script
Cleans EVERYTHING for fresh bulk upload of resumes
"""
import sqlite3
import os
import shutil

DB_PATH = "resumes.db"

print("\n" + "="*70)
print("🗑️  COMPLETE DATABASE RESET")
print("="*70)
print("\n⚠️  This will DELETE ALL data:")
print("   - All parsed resumes")
print("   - All chat history")
print("   - All uploaded documents")
print("   - All vector embeddings (ChromaDB)")
print("\n")

response = input("Are you sure you want to continue? (yes/no): ")

if response.lower() != 'yes':
    print("\n❌ Reset cancelled.")
    exit(0)

print("\n🔄 Starting complete reset...\n")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Delete all message results
print("1️⃣  Deleting message results...")
cursor.execute("DELETE FROM message_results")
deleted_results = cursor.rowcount
print(f"   ✅ Deleted {deleted_results} message results")

# 2. Delete all chat messages
print("2️⃣  Deleting chat messages...")
cursor.execute("DELETE FROM chat_messages")
deleted_messages = cursor.rowcount
print(f"   ✅ Deleted {deleted_messages} chat messages")

# 3. Delete all chat sessions
print("3️⃣  Deleting chat sessions...")
cursor.execute("DELETE FROM chat_sessions")
deleted_sessions = cursor.rowcount
print(f"   ✅ Deleted {deleted_sessions} chat sessions")

# 4. Delete all parsed resumes
print("4️⃣  Deleting parsed resumes...")
cursor.execute("DELETE FROM parsed_resumes")
deleted_resumes = cursor.rowcount
print(f"   ✅ Deleted {deleted_resumes} parsed resumes")

# 5. Delete all documents
print("5️⃣  Deleting all documents...")
cursor.execute("DELETE FROM documents")
deleted_docs = cursor.rowcount
print(f"   ✅ Deleted {deleted_docs} documents")

# 6. Delete all upload batches
print("6️⃣  Deleting upload batches...")
cursor.execute("DELETE FROM upload_batches")
deleted_batches = cursor.rowcount
print(f"   ✅ Deleted {deleted_batches} upload batches")

conn.commit()
conn.close()

# 7. Clear ChromaDB vector store
print("7️⃣  Clearing ChromaDB vector store...")
chroma_path = "storage/chroma"
if os.path.exists(chroma_path):
    try:
        shutil.rmtree(chroma_path)
        print(f"   ✅ ChromaDB cleared (removed {chroma_path})")
    except PermissionError:
        print(f"   ⚠️  Cannot delete ChromaDB - files are in use")
        print(f"   💡 SOLUTION: Close Streamlit and any Python processes, then run:")
        print(f"      Remove-Item -Recurse -Force storage/chroma")
    except Exception as e:
        print(f"   ⚠️  ChromaDB deletion failed: {str(e)}")
        print(f"   💡 Try manually: Remove-Item -Recurse -Force storage/chroma")
else:
    print(f"   ℹ️  ChromaDB directory not found (nothing to clear)")

# 8. Clear uploaded files (optional - uncomment if needed)
# print("8️⃣  Clearing uploaded PDF files...")
# uploads_path = "storage/uploads"
# if os.path.exists(uploads_path):
#     shutil.rmtree(uploads_path)
#     os.makedirs(uploads_path)
#     print(f"   ✅ Uploads directory cleared")

print("\n" + "="*70)
print("✅ DATABASE COMPLETELY RESET!")
print("="*70)
print("\n📋 Summary:")
print(f"   - Message Results: {deleted_results}")
print(f"   - Chat Messages: {deleted_messages}")
print(f"   - Chat Sessions: {deleted_sessions}")
print(f"   - Parsed Resumes: {deleted_resumes}")
print(f"   - Documents: {deleted_docs}")
print(f"   - Upload Batches: {deleted_batches}")
print(f"   - Vector Store: Cleared")
print("\n🎯 Ready for bulk upload! Run:")
print("   python scripts/process_all_resumes.py")
print("="*70 + "\n")
