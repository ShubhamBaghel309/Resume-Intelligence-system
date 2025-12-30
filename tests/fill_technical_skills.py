# scripts/fill_technical_skills.py
import sqlite3
import json

DB_PATH = "resumes.db"

# ============ EDIT THIS LIST ============
# Add candidate names you want to update (leave empty [] to update ALL)
TARGET_CANDIDATES = [
    "Shubham Baghel",
    "Nisarg Rana",
    "Anant Pratap Singh"
]
# ========================================

print("=" * 70)
print("🔧 Filling technical_skills field with all skills")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Build query based on target candidates
if TARGET_CANDIDATES:
    placeholders = ','.join(['?' for _ in TARGET_CANDIDATES])
    query = f"""
        SELECT resume_id, candidate_name, programming_languages, frameworks, tools, technical_skills
        FROM parsed_resumes
        WHERE candidate_name IN ({placeholders})
    """
    cursor.execute(query, TARGET_CANDIDATES)
    print(f"\n🎯 Targeting specific candidates: {', '.join(TARGET_CANDIDATES)}\n")
else:
    cursor.execute("""
        SELECT resume_id, candidate_name, programming_languages, frameworks, tools, technical_skills
        FROM parsed_resumes
    """)
    print(f"\n🌐 Updating ALL candidates\n")

resumes = cursor.fetchall()
total = len(resumes)

if total == 0:
    print("❌ No matching candidates found!")
    conn.close()
    exit()

print(f"📊 Found {total} resume(s) to update\n")

updated_count = 0

for resume_id, name, prog_langs, frameworks, tools, tech_skills in resumes:
    # Parse JSON arrays
    prog_langs_list = json.loads(prog_langs) if prog_langs else []
    frameworks_list = json.loads(frameworks) if frameworks else []
    tools_list = json.loads(tools) if tools else []
    tech_skills_list = json.loads(tech_skills) if tech_skills else []
    
    # Combine all skills
    all_skills = prog_langs_list + frameworks_list + tools_list + tech_skills_list
    
    # Remove duplicates while preserving order
    unique_skills = []
    seen = set()
    for skill in all_skills:
        if skill not in seen:
            unique_skills.append(skill)
            seen.add(skill)
    
    # Update technical_skills field
    cursor.execute("""
        UPDATE parsed_resumes
        SET technical_skills = ?
        WHERE resume_id = ?
    """, (json.dumps(unique_skills), resume_id))
    
    print(f"✅ Updated {name}: {len(unique_skills)} skills")
    updated_count += 1

conn.commit()
conn.close()

print(f"\n🎉 Successfully updated {updated_count}/{total} resume(s)!")
print("✅ technical_skills field now contains all skills combined")