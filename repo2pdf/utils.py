import os
import mimetypes
import json

EXTENSION_LANGUAGE_MAP = {
    # Programming languages
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.cs': 'C#',
    '.rb': 'Ruby',
    '.go': 'Go',
    '.rs': 'Rust',
    '.php': 'PHP',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.m': 'Objective-C',
    '.scala': 'Scala',
    '.sh': 'Shell Script',
    '.bat': 'Batch Script',
    '.ps1': 'PowerShell',
    '.pl': 'Perl',
    '.r': 'R',

    # Web & markup
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'SASS',
    '.less': 'LESS',
    '.json': 'JSON',
    '.xml': 'XML',
    '.yml': 'YAML',
    '.yaml': 'YAML',
    '.md': 'Markdown',

    # Config & data
    '.env': 'Environment Config',
    '.ini': 'INI Config',
    '.conf': 'Config',
    '.cfg': 'Config',
    '.toml': 'TOML Config',
    '.gradle': 'Gradle Build File',
    '.dockerfile': 'Dockerfile',

    # Text & miscellaneous
    '.txt': 'Plain Text',
    '.log': 'Log File',
    '.csv': 'CSV',
    '.tsv': 'TSV',
}


def output_json(files, output_path):
    data = []
    for filename, content in files:
        ext = os.path.splitext(filename)[1]
        language = EXTENSION_LANGUAGE_MAP.get(ext)

        if not language:
            # Fall back to mimetypes
            mime_type, _ = mimetypes.guess_type(filename)
            if mime_type:
                # Use the subtype (e.g. 'plain' from 'text/plain') or mime_type as fallback
                language = mime_type.split('/')[1] if '/' in mime_type else mime_type
            else:
                language = 'Unknown'

        data.append({
            "path": filename,
            "language": language,
            "content": content
        })

    json_path = output_path.replace(".pdf", ".json")
    with open(json_path, 'w') as f:
        json.dump({"files": data}, f, indent=2)

    print(f"✅ JSON saved to {json_path}")
