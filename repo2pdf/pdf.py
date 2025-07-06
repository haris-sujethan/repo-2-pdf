import os
from fpdf import FPDF

def generate_pdf(files, output_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Use bundled font
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "", font_path)
    pdf.set_font("DejaVu", size=10)

    for filename, content in files:
        pdf.add_page()
        pdf.multi_cell(0, 5, f"File: {filename}\n\n{content}")

    pdf.output(output_path)