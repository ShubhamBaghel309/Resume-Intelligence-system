import sqlite3
import sys

# Get raw_text for Vishnu Vikas
conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT raw_text 
    FROM documents 
    WHERE document_id IN (
        SELECT document_id 
        FROM parsed_resumes 
        WHERE candidate_name LIKE '%Vishnu Vikas%'
    )
""")

result = cursor.fetchone()
if result:
    raw_text = result[0]
    
    print("="*70)
    print("CHECKING RAW TEXT FOR VISHNU VIKAS")
    print("="*70)
    
    # Check for key content
    print(f"\n✓ Codeforces mentioned: {'YES' if 'codeforces' in raw_text.lower() else 'NO'}")
    print(f"✓ Interests section: {'YES' if 'interest' in raw_text.lower() else 'NO'}")
    print(f"✓ References section: {'YES' if 'reference' in raw_text.lower() else 'NO'}")
    
    print(f"\n📄 Total raw_text length: {len(raw_text)} characters")
    
    # Show full raw text
    print("\n" + "="*70)
    print("FULL RAW TEXT:")
    print("="*70)
    print(raw_text)
    
else:
    print("No resume found for Vishnu Vikas")

conn.close()
