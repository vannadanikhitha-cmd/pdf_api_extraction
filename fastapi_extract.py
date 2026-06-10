from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pdfplumber
import pandas as pd
import base64
import tempfile
import os

app = FastAPI()


class PDFRequest(BaseModel):
    pdf_base64: str


@app.post("/extract_pdf_tables")
async def extract_pdf_tables(request: PDFRequest):

    try:

        # Decode Base64 PDF
        pdf_bytes = base64.b64decode(
            request.pdf_base64
        )

        # Create temporary PDF
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_pdf:

            temp_pdf.write(pdf_bytes)

            pdf_path = temp_pdf.name

        all_rows = []

        with pdfplumber.open(pdf_path) as pdf:

            for page in pdf.pages:

                words = page.extract_words()

                table_started = False

                current_row_y = None

                row_data = []

                for word in words:

                    text = word["text"]

                    y = round(word["top"])

                    # Detect table header
                    if "TRAN" in text.upper():
                        table_started = True

                    if not table_started:
                        continue

                    if current_row_y is None:

                        current_row_y = y

                    if abs(y - current_row_y) <= 3:

                        row_data.append(text)

                    else:

                        all_rows.append(row_data)

                        row_data = [text]

                        current_row_y = y

                if row_data:

                    all_rows.append(row_data)

        # Remove temp PDF
        os.remove(pdf_path)

        if not all_rows:

            raise HTTPException(
                status_code=404,
                detail="No table data found"
            )

        # Convert to DataFrame
        df = pd.DataFrame(all_rows)

        # Convert DataFrame to JSON
        result = df.fillna("").to_dict(
            orient="records"
        )

        return {
            "status": "success",
            "total_rows": len(result),
            "data": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )