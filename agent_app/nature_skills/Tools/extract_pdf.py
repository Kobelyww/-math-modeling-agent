import pdfplumber
import os

pdf_path = r"d:\Code\python\Mathematical Modeling\D7YWF2MF\Suarez和Murphy - 2012 - Hand gesture recognition with depth images A review.pdf"
output_path = "extracted_text.txt"

if not os.path.exists(pdf_path):
    print(f"Error: File not found at {pdf_path}")
    exit(1)

try:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text += f"--- Page {i+1} ---\n{text}\n\n"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
            
    print(f"Successfully extracted text to {output_path}")
    print(f"Total pages: {len(pdf.pages)}")

except Exception as e:
    print(f"An error occurred: {e}")
