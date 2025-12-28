# scripts/add_skill_columns.py
import sqlite3

DB_PATH = "resumes.db"

print("="*70)
print("Adding New Skill Columns to Database")
print("="*70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(parsed_resumes)")
columns = [row[1] for row in cursor.fetchall()]

new_columns = {
    "programming_languages": "TEXT DEFAULT '[]'",
    "frameworks": "TEXT DEFAULT '[]'",
    "tools": "TEXT DEFAULT '[]'"
}

added_count = 0
for col_name, col_type in new_columns.items():
    if col_name not in columns:
        print(f"  ✅ Adding column: {col_name}")
        cursor.execute(f"ALTER TABLE parsed_resumes ADD COLUMN {col_name} {col_type}")
        added_count += 1
    else:
        print(f"  ⚠️  Column already exists: {col_name}")

conn.commit()
conn.close()

print(f"\n✅ Schema update complete! Added {added_count} new columns.")