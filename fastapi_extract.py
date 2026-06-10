from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import tempfile
import os
import pandas as pd
import pdfplumber
import fitz

from img2table.document import PDF
import pytesseract
import easyocr

app = FastAPI()


class PDFRequest(BaseModel):
    pdf_base64: str


@app.post("/extract_pdf_tables")
async def extract_pdf_tables(request: PDFRequest):

    temp_pdf_path = None

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

        # -------------------------------------------------
        # METHOD 1 : PDFPLUMBER
        # -------------------------------------------------

        with pdfplumber.open(temp_pdf_path) as pdf:

            for page_no, page in enumerate(pdf.pages):

                tables = page.extract_tables()

                for table in tables:

                    if not table or len(table) < 2:
                        continue

                    try:

                        df = pd.DataFrame(
                            table[1:],
                            columns=table[0]
                        )

                        final_tables.append(
                            {
                                "page": page_no + 1,
                                "source": "pdfplumber",
                                "rows": df.fillna("").to_dict(
                                    orient="records"
                                )
                            }
                        )

                    except Exception:
                        pass

        # -------------------------------------------------
        # METHOD 2 : IMG2TABLE + PADDLEOCR
        # If pdfplumber found nothing
        # -------------------------------------------------

        if len(final_tables) == 0:

            reader = easyocr.Reader(['en'])

            pdf_doc = PDF(
                src=temp_pdf_path
            )

            extracted_tables = pdf_doc.extract_tables(
                ocr=ocr,
                implicit_rows=True,
                implicit_columns=True,
                borderless_tables=True
            )

            for page_no, tables in extracted_tables.items():

                for table in tables:

                    try:

                        df = table.df

                        final_tables.append(
                            {
                                "page": page_no,
                                "source": "img2table",
                                "rows": df.fillna("").to_dict(
                                    orient="records"
                                )
                            }
                        )

                    except Exception:
                        pass

        # -------------------------------------------------
        # METHOD 3 : PYMUPDF + IMG2TABLE OCR
        # Last fallback for image PDFs
        # -------------------------------------------------

        if len(final_tables) == 0:

            pdf = fitz.open(
                temp_pdf_path
            )

            image_paths = []

            for page_no in range(len(pdf)):

                page = pdf[page_no]

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(
                        3,
                        3
                    )
                )

                image_path = os.path.join(
                    tempfile.gettempdir(),
                    f"page_{page_no}.png"
                )

                pix.save(
                    image_path
                )

                image_paths.append(
                    image_path
                )

            ocr = PaddleOCR(
                lang="en"
            )

            from img2table.document import Image

            for page_no, image_path in enumerate(image_paths):

                image_doc = Image(
                    src=image_path
                )

                tables = image_doc.extract_tables(
                    ocr=ocr,
                    borderless_tables=True
                )

                for table in tables:

                    try:

                        df = table.df

                        final_tables.append(
                            {
                                "page": page_no + 1,
                                "source": "image_ocr",
                                "rows": df.fillna("").to_dict(
                                    orient="records"
                                )
                            }
                        )

                    except Exception:
                        pass

                if os.path.exists(
                    image_path
                ):
                    os.remove(
                        image_path
                    )

        # -------------------------------------------------
        # NO TABLE FOUND
        # -------------------------------------------------

        if len(final_tables) == 0:

            raise HTTPException(
                status_code=404,
                detail="No tables found in PDF"
            )

        return {
            "status": "success",
            "total_tables": len(
                final_tables
            ),
            "tables": final_tables
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if (
            temp_pdf_path
            and
            os.path.exists(
                temp_pdf_path
            )
        ):
            os.remove(
                temp_pdf_path
            )