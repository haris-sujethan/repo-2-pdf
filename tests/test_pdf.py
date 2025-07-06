import os
import tempfile
from repo2pdf.pdf import generate_pdf

def test_generate_pdf_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.pdf")
        files = [("test.py", "print('hello')")]

        generate_pdf(files, output_path)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0