import os
import shutil
from git import Repo
from repo2pdf.pdf import generate_pdf
import pathspec
from repo2pdf.utils import output_json

def process_local_repo(path, want_json=False, output_path=None, exclude_list=None):
    print(f"Processing local repo at {path}...")
    files = traverse_repo(path, exclude_list or [])
    output_path = output_path or os.path.join(os.getcwd(), "repo_output.pdf")
    generate_pdf(files, output_path)
    print(f"PDF saved to {output_path}")

    if want_json:
        output_json(files, output_path)

def process_remote_repo(url, want_json=False, output_path=None, exclude_list=None, delete=True):
    tmp_dir = "./tmp_repo"
    print(f"Cloning {url} into {tmp_dir}...")
    Repo.clone_from(url, tmp_dir)
    files = traverse_repo(tmp_dir, exclude_list or [])
    output_path = output_path or os.path.join(os.getcwd(), "repo_output.pdf")
    generate_pdf(files, output_path)
    print(f"PDF saved to {output_path}")

    if want_json:
        output_json(files, output_path)

    if delete and os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
        print("Temporary repo deleted")


def traverse_repo(path, exclude_list=[]):
    # Load .gitignore
    gitignore_path = os.path.join(path, '.gitignore')
    spec = None
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            spec = pathspec.PathSpec.from_lines('gitwildmatch', f)

    file_data = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # Skip excluded extensions
            if any(file.endswith(ext) for ext in exclude_list):
                continue

            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, path)

            # Skip ignored files
            if spec and spec.match_file(relative_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                file_data.append((relative_path, content))
            except Exception as e:
                print(f"Skipping {file_path}: {e}")
    return file_data