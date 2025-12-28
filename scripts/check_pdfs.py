# check_pdfs.py
import os

pdf_folder = "downloaded_pdfs"
pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]

print(f"Total PDFs found: {len(pdf_files)}")
print(f"First 5: {pdf_files[:5]}")