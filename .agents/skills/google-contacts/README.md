# Google Contacts Skill (People API)

Autonomous AI skill for interacting with Google Contacts and Phone Books via Google People API v1.

## Features
- Search and list contacts by name, email address, phone number, and company.
- Fetch contact details including multiple phone numbers, emails, addresses, and notes.
- Create new contacts in the Google account address book.
- Delete contacts by `resourceName`.
- Output formatted JSON for agentic workflows and tool-calling pipelines.

## Quick Start
```bash
# List contacts
python scripts/list_contacts.py -n 20 --json

# Search contact
python scripts/list_contacts.py -q "John" --json

# Create contact
python scripts/create_contact.py -n "Alice" -p "+1234567890" -e "alice@example.com" --json
```
