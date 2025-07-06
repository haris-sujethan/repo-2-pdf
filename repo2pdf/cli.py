import inquirer
from repo2pdf.core import process_local_repo, process_remote_repo

def main():
    ascii_art = r"""
                                                 $$$$$$\                          $$\  $$$$$$\  
                                                $$  __$$\                         $$ |$$  __$$\ 
 $$$$$$\   $$$$$$\   $$$$$$\   $$$$$$\          \__/  $$ |         $$$$$$\   $$$$$$$ |$$ /  \__|
$$  __$$\ $$  __$$\ $$  __$$\ $$  __$$\ $$$$$$\  $$$$$$  |$$$$$$\ $$  __$$\ $$  __$$ |$$$$\     
$$ |  \__|$$$$$$$$ |$$ /  $$ |$$ /  $$ |\______|$$  ____/ \______|$$ /  $$ |$$ /  $$ |$$  _|    
$$ |      $$   ____|$$ |  $$ |$$ |  $$ |        $$ |              $$ |  $$ |$$ |  $$ |$$ |      
$$ |      \$$$$$$$\ $$$$$$$  |\$$$$$$  |        $$$$$$$$\         $$$$$$$  |\$$$$$$$ |$$ |      
\__|       \_______|$$  ____/  \______/         \________|        $$  ____/  \_______|\__|      
                    $$ |                                          $$ |                          
                    $$ |                                          $$ |                          
                    \__|                                          \__|                          

Welcome to repo-pdf – convert your repositories to PDFs

Built by Haris

    """
    print(ascii_art)

    repo_type_q = [
        inquirer.List('repo_type',
                      message="Do you want to generate a PDF from a local or remote repo?",
                      choices=['Local', 'Remote'])
    ]
    repo_type = inquirer.prompt(repo_type_q)['repo_type']

    json_q = [
        inquirer.Confirm('json', message="Do you also want to generate a JSON version?", default=True)
    ]
    want_json = inquirer.prompt(json_q)['json']

    output_q = [
        inquirer.Text('output', message="Provide output path for PDF (press enter for current directory)")
    ]
    output_path = inquirer.prompt(output_q)['output']

    exclude_q = [
        inquirer.Text('exclude', message="Enter file extensions to exclude (e.g. .png,.jpg,.exe), or press enter to skip")
    ]
    exclude_input = inquirer.prompt(exclude_q)['exclude']
    exclude_list = [e.strip() for e in exclude_input.split(',')] if exclude_input else []

    if repo_type == 'Local':
        path_q = [
            inquirer.Text('path', message="Provide local repo path (or press enter if in root)")
        ]
        path = inquirer.prompt(path_q)['path']
        process_local_repo(path or '.', want_json, output_path, exclude_list)

    else:
        url_q = [
            inquirer.Text('url', message="Provide GitHub repo URL")
        ]
        url = inquirer.prompt(url_q)['url']

        delete_q = [
            inquirer.Confirm('delete', message="Do you want to delete the cloned repo after PDF generation?", default=True)
        ]
        delete = inquirer.prompt(delete_q)['delete']

        process_remote_repo(url, want_json, output_path, exclude_list, delete)

if __name__ == "__main__":
    main()
