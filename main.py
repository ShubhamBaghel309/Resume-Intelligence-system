# main.py - Main entry point for Resume Intelligence Platform

import sys
from pathlib import Path

# Add app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.db.init_db import init_db

print("🚀 Resume Intelligence Platform")
print("=" * 50)

# Initialize database
print("\n📊 Checking database...")
init_db()

# Check what's in the database
import sqlite3
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

# Count documents
cursor.execute("SELECT COUNT(*) FROM documents")
doc_count = cursor.fetchone()[0]

# Count parsed resumes
cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
parsed_count = cursor.fetchone()[0]

# Count batches
cursor.execute("SELECT COUNT(*) FROM upload_batches")
batch_count = cursor.fetchone()[0]

conn.close()

print(f"\n📈 System Status:")
print(f"   📦 Batches: {batch_count}")
print(f"   📄 Documents: {doc_count}")
print(f"   ✅ Parsed Resumes: {parsed_count}")

print("\n✅ System initialized successfully!")

if __name__ == "__main__":
    print("\n💡 Ready to process resumes!")