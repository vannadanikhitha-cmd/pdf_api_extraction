import os
import json
import numpy as np
import pandas as pd

from pdf2image import convert_from_path
from paddleocr import PaddleOCR

# ==========================================
# CONFIG
# ==========================================

PDF_PATH = r"C:\Users\Hello\Downloads\Axis 925020016590441 pdf.PDF"
POPPLER_PATH = r"C:\poppler\Library\bin\poppler-26.02.0\Library\bin"

# ==========================================
# OCR INITIALIZATION
# ==========================================

ocr = PaddleOCR(
    use_angle_cls=True,
    lang="en"
)

# ==========================================
# OCR PAGE
# ==========================================

def extract_page_words(image):

    image_np = np.array(image)

    result = ocr.ocr(image_np, cls=True)

    words = []

    if not result:
        print("No OCR text detected")
        return words

    if result[0] is None:
        return words

    for line in result[0]:

        box = line[0]
        text = line[1][0]
        score = line[1][1]

        x1 = int(box[0][0])
        y1 = int(box[0][1])

        x2 = int(box[2][0])
        y2 = int(box[2][1])

        words.append({
            "text": text,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "score": float(score)
        })

    return words

# ==========================================
# GROUP INTO ROWS
# ==========================================

def group_rows(words, y_threshold=15):

    words = sorted(
        words,
        key=lambda x: (x["y1"], x["x1"])
    )

    rows = []
    current_row = []
    current_y = None

    for word in words:

        if current_y is None:

            current_y = word["y1"]
            current_row.append(word)

        elif abs(word["y1"] - current_y) <= y_threshold:

            current_row.append(word)

        else:

            rows.append(current_row)

            current_row = [word]
            current_y = word["y1"]

    if current_row:
        rows.append(current_row)

    return rows

# ==========================================
# ROWS TO TABLE
# ==========================================

def rows_to_table(rows):

    table = []

    for row in rows:

        row = sorted(
            row,
            key=lambda x: x["x1"]
        )

        table.append(
            [item["text"] for item in row]
        )

    return table
# ==========================================
# TABLE TO JSON
# ==========================================

def table_to_json(rows):

    if not rows:
        return []

    headers = rows[0]

    transactions = []

    for row in rows[1:]:

        record = {}

        for i in range(len(headers)):

            if i < len(row):
                record[headers[i]] = row[i]
            else:
                record[headers[i]] = ""

        transactions.append(record)

    return transactions

# ==========================================
# PDF PROCESSING
# ==========================================

def process_pdf(pdf_path):

    pages = convert_from_path(
        pdf_path,
        poppler_path=POPPLER_PATH
    )

    all_rows = []

    for page_no, page in enumerate(pages, start=1):

        print(f"Processing Page {page_no}")

        words = extract_page_words(page)

        rows = group_rows(words)

        table = rows_to_table(rows)

        all_rows.extend(table)

    return all_rows

# ==========================================
# SAVE JSON
# ==========================================

def save_json(data):

    os.makedirs("output", exist_ok=True)

    with open(
        "output/transactions.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(
        "\nSaved : output/transactions.json"
    )
# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    extracted_rows = process_pdf(PDF_PATH)

    transactions = table_to_json(extracted_rows)

    save_json(transactions)

    print(
        json.dumps(
            transactions[:5],
            indent=4,
            ensure_ascii=False
        )
    )