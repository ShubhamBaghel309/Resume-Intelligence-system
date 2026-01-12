# Diagnostic: Show the difference between hardcoded fields vs full resume coverage

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sqlite3
import json

def show_missing_data():
    """Show what information is LOST when we only use hardcoded fields"""
    
    print("\n" + "="*80)
    print("🔍 WHY WE NEEDED THIS FIX: Hardcoded Fields vs. Full Resume")
    print("="*80)
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resumes.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get a sample resume
    cursor.execute("""
        SELECT pr.*, d.raw_text 
        FROM parsed_resumes pr
        JOIN documents d ON pr.document_id = d.document_id
        WHERE pr.candidate_name LIKE '%BINEESHA%'
        LIMIT 1
    """)
    
    resume = cursor.fetchone()
    conn.close()
    
    if not resume:
        print("❌ BINEESHA not found!")
        return
    
    print(f"\n📄 Candidate: {resume['candidate_name']}\n")
    
    # Show what we HAVE in hardcoded fields
    print("=" * 80)
    print("✅ CAPTURED IN HARDCODED FIELDS (skills, work_experience, education, projects)")
    print("=" * 80)
    
    fields = ['skills', 'work_experience', 'education', 'projects', 
              'email', 'phone', 'location', 'total_experience_years', 'current_role']
    
    for field in fields:
        value = resume[field]
        if value:
            if isinstance(value, str) and value.startswith('['):
                # JSON array
                try:
                    items = json.loads(value)
                    print(f"\n{field.upper()}: ({len(items)} items)")
                    for item in items[:2]:  # Show first 2
                        if isinstance(item, dict):
                            print(f"  - {list(item.values())[:3]}")
                        else:
                            print(f"  - {item}")
                except:
                    print(f"\n{field.upper()}: {str(value)[:100]}")
            else:
                print(f"\n{field.upper()}: {value}")
    
    # Now show what's in raw_text that's NOT in hardcoded fields
    print("\n\n" + "=" * 80)
    print("⚠️  MISSING/LOST IN HARDCODED FIELDS (only in raw_text)")
    print("=" * 80)
    
    raw_text = resume['raw_text']
    
    # Keywords to search for
    keywords_map = {
        "REFERENCES": ["reference", "available on request", "available upon request"],
        "LANGUAGES": ["language", "speak", "fluent", "proficient", "native"],
        "DRIVING LICENSE": ["driving", "license", "licence", "driver"],
        "HOBBIES/INTERESTS": ["hobby", "hobbies", "interest", "interests", "leisure"],
        "AWARDS/HONORS": ["award", "honor", "honour", "prize", "recognition"],
        "PUBLICATIONS": ["publication", "published", "paper", "journal"],
        "CERTIFICATIONS": ["certification", "certified", "certificate"],
        "CODING PLATFORMS": ["leetcode", "codeforces", "hackerrank", "codechef", "github"],
    }
    
    found_sections = []
    
    for section_name, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword.lower() in raw_text.lower():
                # Extract context around the keyword
                idx = raw_text.lower().index(keyword.lower())
                start = max(0, idx - 80)
                end = min(len(raw_text), idx + 150)
                context = raw_text[start:end].strip()
                
                print(f"\n🔍 Found '{section_name}':")
                print(f"   Context: ...{context}...")
                found_sections.append(section_name)
                break  # Don't repeat same section
    
    if not found_sections:
        print("\n✅ No additional sections found (or resume is fully structured)")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("💡 SUMMARY")
    print("=" * 80)
    print(f"""
Before Fix:
- Hardcoded fields: ✅ Skills, Work Experience, Education, Projects
- Missing: ❌ {', '.join(found_sections) if found_sections else 'Nothing'}
- Result: Agent couldn't answer questions about {found_sections[0] if found_sections else 'additional info'}

After Fix:
- For 1-2 candidates: ✅ Full raw_text included
- Agent can now answer: ✅ ANY question about the resume
- No more "not specified" for data that IS there!
    """)

if __name__ == "__main__":
    show_missing_data()
