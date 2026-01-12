import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from app.utils.experience_calculator import calculate_years_of_experience
import json

DB_PATH = "resumes.db"

print("=" * 70)
print("Database Migration: Add additional_information field and recalculate years")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Step 1: Add additional_information column if it doesn't exist
print("\n📊 Adding additional_information column...")
try:
    cursor.execute("""
        ALTER TABLE parsed_resumes 
        ADD COLUMN additional_information TEXT
    """)
    conn.commit()
    print("✅ Column added successfully")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("⚠️  Column already exists, skipping...")
    else:
        raise

# Step 2: Recalculate total_experience_years for resumes that have 0 or NULL
print("\n🔄 Recalculating work experience years for candidates...")

cursor.execute("""
    SELECT resume_id, candidate_name, work_experience, total_experience_years
    FROM parsed_resumes
    WHERE total_experience_years IS NULL OR total_experience_years = 0
""")

candidates_to_update = cursor.fetchall()

if not candidates_to_update:
    print("✅ All candidates already have experience years calculated")
else:
    print(f"Found {len(candidates_to_update)} candidates needing calculation\n")
    
    updated_count = 0
    for resume_id, candidate_name, work_json, current_years in candidates_to_update:
        try:
            # Parse work experience
            work_experience = json.loads(work_json) if work_json else []
            
            if not work_experience:
                print(f"   ⚠️  {candidate_name}: No work experience data")
                continue
            
            # Calculate years
            calculated_years = calculate_years_of_experience(work_experience)
            
            if calculated_years:
                # Update database
                cursor.execute("""
                    UPDATE parsed_resumes
                    SET total_experience_years = ?
                    WHERE resume_id = ?
                """, (calculated_years, resume_id))
                
                print(f"   ✅ {candidate_name}: {calculated_years} years")
                updated_count += 1
            else:
                print(f"   ⚠️  {candidate_name}: Could not calculate from dates")
                
        except Exception as e:
            print(f"   ❌ {candidate_name}: Error - {e}")
    
    conn.commit()
    print(f"\n✅ Updated {updated_count}/{len(candidates_to_update)} candidates")

conn.close()

print("\n" + "=" * 70)
print("✅ Migration Complete!")
print("=" * 70)
print("\nNext steps:")
print("1. Re-parse any new resumes to extract additional_information")
print("2. Re-index resumes to include the new additional_information chunks")
print("3. Test the agent with queries about achievements, awards, references, etc.")
