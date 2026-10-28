# Google Calendar Skill

Autonomous AI skill for interacting with Google Calendar via Google Calendar API v3.

## Features
- List upcoming events, daily and weekly agendas.
- Query and filter events by title, description, and date range.
- Create new events with start/end time, description, location, and attendees.
- Delete events by event ID.
- Supports `--json` flag for automated LLM processing.

## Quick Start
```bash
# Get upcoming week events
python scripts/list_events.py -d 7 --json

# Create meeting
python scripts/create_event.py -s "Team Sync" --start "2026-10-28T14:00:00+02:00" --end "2026-10-28T15:00:00+02:00" --json

# Delete event
python scripts/delete_event.py -i <EVENT_ID> --json
```
