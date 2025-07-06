import os
import tempfile
from repo2pdf.core import traverse_repo
import os
import tempfile
from repo2pdf.core import process_local_repo

def test_traverse_repo_reads_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy file
        file_path = os.path.join(tmpdir, "test.py")
        with open(file_path, "w") as f:
            f.write("print('hello')")

        files = traverse_repo(tmpdir)

        assert len(files) == 1
        assert files[0][0] == "test.py"
        assert "print('hello')" in files[0][1]

def test_traverse_repo_excludes_specified_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two files: one .py and one .png
        py_path = os.path.join(tmpdir, "test.py")
        png_path = os.path.join(tmpdir, "image.png")

        with open(py_path, "w") as f:
            f.write("print('hello')")

        with open(png_path, "w") as f:
            f.write("binarydata")

        from repo2pdf.core import traverse_repo
        files = traverse_repo(tmpdir)

        # Default traverse_repo (no exclude param) should return both files
        assert any(f[0] == "test.py" for f in files)

        # Now test excluding .png
        files_exclude = traverse_repo(tmpdir, exclude_list=[".png"])
        assert any(f[0] == "test.py" for f in files_exclude)
        assert not any(f[0] == "image.png" for f in files_exclude)

def test_process_remote_repo_clones_and_generates(monkeypatch):
    from repo2pdf.core import process_remote_repo
    import tempfile
    import os

    # Use a very small public GitHub repo for testing
    test_repo_url = "https://github.com/octocat/Hello-World.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.pdf")

        # Monkeypatch os.getcwd to tmpdir so output is saved there
        monkeypatch.setattr(os, "getcwd", lambda: tmpdir)

        # Run process_remote_repo with delete=True to clean up after test
        process_remote_repo(test_repo_url, want_json=True, output_path=output_path, exclude_list=[], delete=True)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

        json_path = output_path.replace(".pdf", ".json")
        assert os.path.exists(json_path)

def test_process_local_repo_creates_outputs(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy local repo file
        file_path = os.path.join(tmpdir, "test.py")
        with open(file_path, "w") as f:
            f.write("print('hello')")

        output_path = os.path.join(tmpdir, "repo_output.pdf")

        # Monkeypatch os.getcwd to tmpdir so outputs are saved there
        monkeypatch.setattr(os, "getcwd", lambda: tmpdir)

        # Run process_local_repo with JSON generation
        process_local_repo(tmpdir, want_json=True)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

        json_path = output_path.replace(".pdf", ".json")
        assert os.path.exists(json_path)
