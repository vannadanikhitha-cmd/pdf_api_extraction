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

        pdf_bytes = base64.b64decode(
            request.pdf_base64
        )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_pdf:

            temp_pdf.write(pdf_bytes)
            pdf_path = temp_pdf.name

        final_data = []

        with pdfplumber.open(pdf_path) as pdf:

            for page in pdf.pages:

                # Method 1
                tables = page.extract_tables()

                if tables:

                    for table in tables:

                        if len(table) > 1:

                            df = pd.DataFrame(
                                table[1:],
                                columns=table[0]
                            )

                            final_data.extend(
                                df.fillna("").to_dict(
                                    orient="records"
                                )
                            )

                else:

                    # Method 2
                    words = page.extract_words()

                    if words:

                        rows = {}

                        for word in words:

                            y = round(word["top"])

                            rows.setdefault(
                                y,
                                []
                            ).append(
                                word["text"]
                            )

                        for y in sorted(rows):

                            row_text = " ".join(
                                rows[y]
                            )

                            final_data.append(
                                {
                                    "row_data": row_text
                                }
                            )

        os.remove(pdf_path)

        if not final_data:

            raise HTTPException(
                status_code=404,
                detail="No table/text found"
            )

        return {
            "status": "success",
            "total_rows": len(final_data),
            "data": final_data
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )