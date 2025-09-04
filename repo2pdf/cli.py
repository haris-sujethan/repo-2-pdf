# repo2pdf/cli.py
from __future__ import annotations

import inquirer
from repo2pdf.core import process_local_repo, process_remote_repo

def main():
    ascii_art = r"""
 ______   ______  ______  ______           _____           ______  ______  ______    
/_____/\ /_____/\/_____/\/_____/\         /_____/\        /_____/\/_____/\/_____/\   
\:::_ \ \\::::_\/\:::_ \ \:::_ \ \  ______\:::_:\ \ ______\:::_ \ \:::_ \ \::::_\/_  
 \:(_) ) )\:\/___/\:(_) \ \:\ \ \ \/______/\  _\:\|/______/\:(_) \ \:\ \ \ \:\/___/\ 
  \: __ `\ \::___\/\: ___\/\:\ \ \ \__::::\/ /::_/_\__::::\/\: ___\/\:\ \ \ \:::._\/ 
   \ \ `\ \ \:\____/\ \ \   \:\_\ \ \        \:\____/\       \ \ \   \:\/.:| \:\ \   
    \_\/ \_\/\_____\/\_\/    \_____\/         \_____\/        \_\/    \____/_/\_\/   
                                                                                                
Welcome to repo2pdf – convert your repositories to PDFs
    """
    print(ascii_art)

    repo_type_q = [
        inquirer.List(
            "repo_type",
            message="Do you want to generate a PDF from a local or remote repo?",
            choices=["Local", "Remote"],
        )
    ]
    repo_type = inquirer.prompt(repo_type_q)["repo_type"]

    json_q = [inquirer.Confirm("json", message="Do you also want to generate a JSON version?", default=False)]
    want_json = inquirer.prompt(json_q)["json"]

    output_q = [inquirer.Text("output", message="Provide output path for PDF (press enter for default)")]
    output_path = inquirer.prompt(output_q)["output"]

    exclude_q = [inquirer.Text("exclude", message="Enter file extensions to exclude (e.g. .png,.jpg,.exe), or press enter to skip")]
    exclude_input = inquirer.prompt(exclude_q)["exclude"]
    exclude_list = [e.strip() for e in exclude_input.split(",")] if exclude_input else []

    if repo_type == "Local":
        path_q = [inquirer.Text("path", message="Provide local repo path (or press enter if current directory)")]
        path = inquirer.prompt(path_q)["path"]
        process_local_repo(path, want_json, output_path, exclude_list)
    else:
        url_q = [inquirer.Text("url", message="Provide GitHub repo URL (e.g. https://github.com/user/repo)")]
        url = inquirer.prompt(url_q)["url"]
        process_remote_repo(url, want_json, output_path, exclude_list)

if __name__ == "__main__":
    main()
