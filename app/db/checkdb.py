# check_db.py
import sqlite3

conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()

# Check what tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in database:")
for table in tables:
    print(f"  - {table[0]}")

# Check parsed_resumes schema if it exists
try:
    cursor.execute("PRAGMA table_info(parsed_resumes)")
    columns = cursor.fetchall()
    print("\nColumns in parsed_resumes:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
except:
    print("\nparsed_resumes table doesn't exist!")


try:
    cursor.execute("PRAGMA table_info(upload_batches)")
    columns = cursor.fetchall()
    print("\nColumns in upload_batches:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
except:
    print("\nupload_batches table doesn't exist!")

try:
    cursor.execute("PRAGMA table_info(documents)")
    columns = cursor.fetchall()
    print("\nColumns in documents:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
except:
    print("\ndocuments table doesn't exist!")
# Check how many resumes
try:
    cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
    count = cursor.fetchone()[0]
    print(f"\nTotal resumes: {count}")
except:
    pass

conn.close()