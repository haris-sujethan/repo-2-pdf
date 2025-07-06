import os
import tempfile
import json
from repo2pdf.utils import output_json

def test_output_json_creates_valid_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.pdf")
        files = [("test.py", "print('hello')")]

        output_json(files, output_path)

        json_path = output_path.replace(".pdf", ".json")
        assert os.path.exists(json_path)

        with open(json_path) as f:
            data = json.load(f)
            assert "files" in data
            assert data["files"][0]["path"] == "test.py"
            assert "print('hello')" in data["files"][0]["content"]