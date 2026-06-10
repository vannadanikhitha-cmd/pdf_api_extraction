from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import tempfile
import os
import pandas as pd
import pdfplumber
import fitz
import easyocr
import traceback

app = FastAPI()

class PDFRequest(BaseModel):
    pdf_base64: str

@app.post("/extract_pdf_tables")
async def extract_pdf_tables(request: PDFRequest):


    pdf_path = None
    image_paths = []

try:

    # Decode Base64 PDF
    pdf_bytes = base64.b64decode(
        request.pdf_base64
    )

    # Save PDF temporarily
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ) as temp_pdf:

        temp_pdf.write(pdf_bytes)
        temp_pdf_path = temp_pdf.name

    final_tables = []

    # =====================================
    # METHOD 1 : PDFPLUMBER
    # =====================================

    with pdfplumber.open(temp_pdf_path) as pdf:

        for page_no, page in enumerate(pdf.pages):

            table_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "edge_min_length": 3,
                "intersection_tolerance": 3
            }

            tables = page.extract_tables(
                table_settings=table_settings
            )

            for table in tables:

                if not table:
                    continue

                try:

                    cleaned_table = []

                    for row in table:

                        if row and any(
                            cell is not None and str(cell).strip()
                            for cell in row
                        ):
                            cleaned_table.append(row)

                    if len(cleaned_table) < 2:
                        continue

                    headers = []

                    for i, col in enumerate(cleaned_table[0]):

                        if col and str(col).strip():

                            headers.append(
                                str(col).strip()
                            )

                        else:

                            headers.append(
                                f"Column_{i+1}"
                            )

                    df = pd.DataFrame(
                        cleaned_table[1:],
                        columns=headers
                    )

                    df = df.fillna("")

                    final_tables.append(
                        {
                            "page": page_no + 1,
                            "source": "pdfplumber",
                            "rows": df.to_dict(
                                orient="records"
                            )
                        }
                    )

                except Exception as table_error:

                    print(
                        f"Table Error: {table_error}"
                    )

    # =====================================
    # METHOD 2 : OCR FALLBACK
    # =====================================

    if len(final_tables) == 0:

        reader = easyocr.Reader(
            ['en'],
            gpu=False
        )

        pdf = fitz.open(
            temp_pdf_path
        )

        for page_no in range(len(pdf)):

            page = pdf[page_no]

            pix = page.get_pixmap(
                matrix=fitz.Matrix(3, 3)
            )

            image_path = os.path.join(
                tempfile.gettempdir(),
                f"page_{page_no}.png"
            )

            pix.save(image_path)

            image_paths.append(
                image_path
            )

            try:

                results = reader.readtext(
                    image_path,
                    detail=0
                )

                rows = []

                for line in results:

                    line = line.strip()

                    if line:

                        rows.append(
                            {
                                "text": line
                            }
                        )

                if rows:

                    final_tables.append(
                        {
                            "page": page_no + 1,
                            "source": "easyocr",
                            "rows": rows
                        }
                    )

            except Exception:
                pass

    # =====================================
    # NO TABLE FOUND
    # =====================================

    if len(final_tables) == 0:

        raise HTTPException(
            status_code=404,
            detail="No tables found in PDF"
        )

        return {
            "status": "success",
            "total_tables": len(final_tables),
            "tables": final_tables
         }

except Exception as e:

    traceback.print_exc()

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )

finally:

    try:

        if (
            temp_pdf_path
            and
            os.path.exists(temp_pdf_path)
        ):
            os.remove(temp_pdf_path)

        for image_path in image_paths:

            if os.path.exists(image_path):
                os.remove(image_path)

    except Exception as cleanup_error:

        print(
            f"Cleanup Error: {cleanup_error}"
        )

