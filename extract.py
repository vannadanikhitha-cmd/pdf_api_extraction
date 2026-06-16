from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import pdfplumber
import pandas as pd
import base64
import tempfile
import os

app = FastAPI()


class PDFRequest(BaseModel):
    file_name: str
    pdf_base64: str


@app.post("/extract_tables")
async def pdf_to_csv(request: PDFRequest):

    try:
        # Decode Base64 PDF
        pdf_bytes = base64.b64decode(request.pdf_base64)

        # Create temporary PDF
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_pdf:

            temp_pdf.write(pdf_bytes)
            pdf_path = temp_pdf.name

        all_rows = []

        # Extract tables
        with pdfplumber.open(pdf_path) as pdf:

            for page in pdf.pages:

                table = page.extract_table()

                if table:

                    if not all_rows:
                        all_rows.extend(table)
                    else:
                        all_rows.extend(table[1:])

        # Delete temporary PDF
        os.remove(pdf_path)

        if not all_rows:
            raise HTTPException(
                status_code=404,
                detail="No table found in PDF"
            )

        # Create DataFrame
        df = pd.DataFrame(
            all_rows[1:],
            columns=all_rows[0]
        )

        # Convert DataFrame to JSON
        json_data = df.to_dict(orient="records")

        return {
            "status": "success",
            "file_name": request.file_name,
            "total_rows": len(json_data),
            "data": json_data
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )