import pdfplumber
import sqlite3
from app.db.init_db import DB_PATH

def extract_text_from_pdf(file_path:str)->str:
    """ extract text from a pdf file"""
    if file_path.endswith('.pdf') is False:
        raise ValueError("File is not a PDF")
    with pdfplumber.open(file_path) as pdf:
        text=""
        for page in pdf.pages:
            text+=page.extract_text() + "\n"
    if(text.strip() == ""):
        raise ValueError("No text found in PDF")
    return text

def save_extracted_text(document_id:str,text:str):
    """save extracted text to the database"""
    conn=sqlite3.connect(DB_PATH)
    cursor=conn.cursor()
    cursor.execute("""
        UPDATE documents
        SET raw_text = ?
        WHERE document_id = ?
    """, (text, document_id))
    # now update the status from uploaded to extracted
    cursor.execute("""
        UPDATE documents
        SET status = ?
        WHERE document_id = ?
    """, ("extracted", document_id))
    conn.commit()
    conn.close()

def process_batch(batch_id:str):
    """process all documents in a batch to extract text"""
    conn=sqlite3.connect(DB_PATH)
    cursor=conn.cursor()
    cursor.execute("""
        SELECT document_id, file_path FROM documents
        WHERE batch_id = ?
    """, (batch_id,))
    documents=cursor.fetchall()
    conn.close()
    for document in documents:
        document_id, file_path = document
        try:
            text=extract_text_from_pdf(file_path)
            save_extracted_text(document_id, text)
            print(f"Extracted text for document {document_id}")
        except Exception as e:
            print(f"Failed to extract text for document {document_id}: {e}")