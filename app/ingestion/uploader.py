import uuid
import sqlite3
from pathlib import Path

DB_PATH = "resumes.db"
UPLOAD_ROOT = Path("resumedata/resumedata")


def create_upload_batch(recruiter_id: str, upload_type: str, total_files: int):
    batch_id = str(uuid.uuid4())

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO upload_batches (batch_id, recruiter_id, upload_type, total_files)
        VALUES (?, ?, ?, ?)
    """, (batch_id, recruiter_id, upload_type, total_files))

    conn.commit()
    conn.close()

    batch_folder = UPLOAD_ROOT / batch_id
    batch_folder.mkdir(parents=True, exist_ok=True)

    return batch_id, batch_folder


def register_document(batch_id: str, filename: str, file_path: str):
    document_id = str(uuid.uuid4())

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO documents (document_id, batch_id, original_filename, file_path, status)
        VALUES (?, ?, ?, ?, ?)
    """, (document_id, batch_id, filename, file_path, "uploaded"))

    conn.commit()
    conn.close()


def store_uploaded_pdfs(pdf_paths: list[Path], recruiter_id: str):
    batch_id, batch_folder = create_upload_batch(
        recruiter_id=recruiter_id,
        upload_type="multi_pdf",
        total_files=0  # temporary
    )

    count = 0
    for pdf_path in pdf_paths:
        target_path = batch_folder / pdf_path.name
        target_path.write_bytes(pdf_path.read_bytes())

        register_document(
            batch_id=batch_id,
            filename=pdf_path.name,
            file_path=str(target_path)
        )
        count += 1

    update_batch_file_count(batch_id, count)
    return batch_id


def update_batch_file_count(batch_id: str, total_files: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE upload_batches
        SET total_files = ?
        WHERE batch_id = ?
    """, (total_files, batch_id))

    conn.commit()
    conn.close()
