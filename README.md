# repo-2-pdf

CLI tool to convert your repositories into clean PDFs and structured JSON outputs, **designed for giving LLMs full context of your codebase**

## Features

- Convert **local** or **remote GitHub repositories**
- Generate **PDFs** containing full file structures and contents
- Output structured **JSON summaries**
- Exclude unnecessary file types automatically

## Installation

### Option 1: Install from [PyPI](https://pypi.org/project/repo2pdf/) (Recommended)

```bash
pip install repo2pdf
```

### Option 2: Install from Source

Clone the repository and install locally:

```bash
git clone https://github.com/haris-sujethan/repo-2-pdf
cd repo-2-pdf
pip install -r requirements.txt
```

Then choose one of the following:

**Local development install (recommended):**

```bash
pip install -e .
repo2pdf
```

**Run without installing:**

```bash
python -m repo2pdf.cli
```

## Usage

Run the CLI tool:

```bash
repo2pdf
```

**Follow the interactive prompts:**

1. Select local or remote repository
2. Provide the local repo path or GitHub URL
3. Choose an output location
4. Exclude any file types you don't want included (e.g., `.png`, `.jpg`)
5. Optionally generate a JSON summary alongside the PDF

## Example CLI Flow

<img src="https://raw.githubusercontent.com/haris-sujethan/repo-2-pdf/main/repo2pdf/docs/images/example-CLI.png" alt="Example CLI Interface" width="850"/>

## Example Outputs

Example outputs are available in the `/examples` folder:

- **repo_output.pdf**
- **repo_output.json** 
