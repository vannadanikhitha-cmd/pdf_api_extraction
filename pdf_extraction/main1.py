import json
import re
import pdfplumber

all_rows = []


def is_valid_date(text):
    """Generically checks if a string contains a date pattern.

    Matches formats like: DD/MM/YY, DD/MM/YYYY, DD-MM-YYYY, etc.
    """
    if not text:
        return False
    # Regular expression for matching common date formats found in statements
    date_pattern = r"\b\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4}\b"
    return bool(re.search(date_pattern, text))


with pdfplumber.open(r"C:\Users\Hello\Downloads\hdfc.pdf") as pdf:
    global_headers = []
    global_columns = []
    current_row = None

    for page_num, page in enumerate(pdf.pages, start=1):
        detected_tables = page.find_tables()

        if not detected_tables:
            continue

        table_obj = detected_tables[0]
        table_top = table_obj.bbox[1]
        table_bottom = table_obj.bbox[3]

        raw_table_data = table_obj.extract()

        if raw_table_data and page_num == 1:
            global_headers = [
                str(cell).strip().replace("\n", " ")
                for cell in raw_table_data[0]
            ]

            x_coordinates = sorted(
                list(
                    set(
                        [cell[0] for cell in table_obj.cells]
                        + [cell[2] for cell in table_obj.cells]
                    )
                )
            )

            global_columns = []
            for i in range(len(x_coordinates) - 1):
                if i < len(global_headers):
                    global_columns.append(
                        {
                            "name": global_headers[i],
                            "x0": x_coordinates[i],
                            "x1": x_coordinates[i + 1],
                        }
                    )

        if not global_columns:
            continue

        words = page.extract_words()

        tolerance = 5
        lines = []
        
        # --- FIX 1: Lower the threshold from 15 to 5 to catch rows printed tightly against the header ---
        header_height_threshold = table_top

        for word in words:
            if word["top"] > table_bottom:
                continue
            if word["top"] < header_height_threshold:
                continue
            if (
                word["x0"] < table_obj.bbox[0]
                or word["x1"] > table_obj.bbox[2]
            ):
                continue

            found = False
            for line in lines:
                if abs(word["top"] - line["top"]) <= tolerance:
                    line["words"].append(word)
                    found = True
                    break
            if not found:
                lines.append({"top": word["top"], "words": [word]})

        lines.sort(key=lambda x: x["top"])
        print(f"\nPAGE {page_num}") 
        for line in lines[:5]: 
            print( 
                line["top"], 
                " ".join(w["text"] for w in line["words"]) 
            )
        # Dynamically identify which column is the Date column and which is Description
        date_col_name = global_columns[0]["name"]
        desc_col_name = None

        for col in global_columns:
            col_lower = col["name"].lower()
            if "date" in col_lower:
                date_col_name = col["name"]
            elif (
                "description" in col_lower
                or "narration" in col_lower
                or "particulars" in col_lower
            ):
                desc_col_name = col["name"]

        if not desc_col_name and len(global_columns) > 1:
            desc_col_name = global_columns[1]["name"]

        for line in lines:
            line_data = {col["name"]: "" for col in global_columns}
            line["words"].sort(key=lambda x: x["x0"])

            # Map words to columns
            for word in line["words"]:
                midpoint = (word["x0"] + word["x1"]) / 2
                for col in global_columns:
                    if col["x0"] <= midpoint <= col["x1"]:
                        line_data[col["name"]] += " " + word["text"]
                        break

            line_data = {k: v.strip() for k, v in line_data.items()}

            if not any(line_data.values()):
                continue

            # Skip header rows repeating across pages
            row_text = " ".join(line_data.values()).lower()

            if (
                "date" in row_text
                and (
                    "description" in row_text
                    or "narration" in row_text
                    or "particulars" in row_text
                )
            ):
                continue
            # Core Logic: Use RegEx to verify if the text in the date column is actually a valid date string
            date_text = line_data.get(date_col_name, "").replace(" ", "")
            has_valid_date = is_valid_date(date_text)

            if has_valid_date:
                # Start a clean new transaction record
                if current_row:
                    if desc_col_name and current_row.get(desc_col_name):
                        current_row[desc_col_name] = re.sub(
                            r"\s+[A-Z_]{5,}\s*[:-]*\s*$",
                            "",
                            current_row[desc_col_name],
                        ).strip()
                    all_rows.append(current_row)
                current_row = line_data
            else:
                # STRUCTURAL CHECK: This row lacks a date. Is it a transaction continuation or a summary footer?
                if current_row:
                    is_pure_description_continuation = True

                    for col_name, col_value in line_data.items():
                        if col_name != desc_col_name and col_value != "":
                            is_pure_description_continuation = False
                            break

                    if is_pure_description_continuation:
                        if line_data.get(desc_col_name):
                            current_row[desc_col_name] = (
                                current_row[desc_col_name]
                                + " "
                                + line_data[desc_col_name]
                            ).strip()
                    else:
                        # --- FIX 2: Check if leakage looks like actual footer summary text ---
                        # If it contains multi-column items but doesn't look like a real statement summary footer, 
                        # don't completely discard the active record tracking flow prematurely.
                        combined_text = " ".join(line_data.values()).lower()
                        if "summary" in combined_text or "balance" in combined_text or "count" in combined_text:
                            if desc_col_name and current_row.get(desc_col_name):
                                current_row[desc_col_name] = re.sub(
                                    r"\s+[A-Z_]{5,}\s*[:-]*\s*$",
                                    "",
                                    current_row[desc_col_name],
                                ).strip()

                            all_rows.append(current_row)
                            current_row = None

    if current_row:
        if desc_col_name and current_row.get(desc_col_name):
            current_row[desc_col_name] = re.sub(
                r"\s+[A-Z_]{5,}\s*[:-]*\s*$", "", current_row[desc_col_name]
            ).strip()
        all_rows.append(current_row)

# Save result
output_file = "hdfc1.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_rows, f, indent=4, ensure_ascii=False)

print(f"Generic Processing Complete! Total rows saved: {len(all_rows)}")
print(f"Total number of JSON rows extracted: {len(all_rows)}")