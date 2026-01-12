import sqlite3
conn = sqlite3.connect("resumes.db")
cursor = conn.cursor()
cursor.execute("SELECT candidate_name, total_experience_years FROM parsed_resumes WHERE total_experience_years >= 10")
print(cursor.fetchall())
conn.close()