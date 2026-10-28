# Google Mail Skill (Gmail API)

Autonomous AI skill for interacting with Google Gmail via Google API Client Discovery.

## Features
- Search and query messages with standard Gmail query syntax (`is:unread`, `from:`, `subject:`, etc.).
- Read full email contents, text, HTML, headers, and attachment metadata.
- Send plaintext and HTML emails with multiple file attachments.
- Manage message labels and move to trash.
- Safe OAuth 2.0 token handling integrated with `src.ai.google_accounts_state`.

## Quick Start
```bash
# List recent emails
python scripts/list_messages.py -n 5 --json

# Read an email by ID
python scripts/read_message.py -i <MSG_ID> --json

# Send an email
python scripts/send_message.py -t "target@domain.com" -s "Title" -b "Hello" --json
```
