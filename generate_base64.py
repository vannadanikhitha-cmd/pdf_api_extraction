import base64

pdf_path = r"C:\Users\Hello\Downloads\06450200001031 Jan'26 - Feb'26.pdf"

with open(pdf_path, "rb") as file:
    pdf_base64 = base64.b64encode(
        file.read()
    ).decode("utf-8")

with open("pdf_base64.txt", "w") as output:
    output.write(pdf_base64)

print("Base64 file created successfully")