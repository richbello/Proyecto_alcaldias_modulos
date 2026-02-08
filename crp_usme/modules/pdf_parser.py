# modules/pdf_parser.py
import io
import pdfplumber

def extract_rows_from_pdf(pdf_bytes: bytes):
    rows = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if row and isinstance(row, list):
                        rows.append(row)
    return rows