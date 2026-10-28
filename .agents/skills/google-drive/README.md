# Google Drive Skill

Autonomous AI skill for interacting with Google Drive via Google Drive API v3.

## Features
- Search and query files across Google Drive with advanced query filters.
- List folders and nested directory contents.
- Upload local files to specific Drive folders with auto-resumable upload.
- Download cloud files and export Google Docs/Sheets to standard file formats.
- Complete CLI suite with `--json` output format for agentic pipelines.

## Quick Start
```bash
# Search files
python scripts/list_files.py -q "name contains 'Project'" --json

# Upload a file
python scripts/upload_file.py -f "path/to/report.pdf" --json

# Download a file
python scripts/download_file.py -i <FILE_ID> -o "path/to/save.pdf" --json
```
