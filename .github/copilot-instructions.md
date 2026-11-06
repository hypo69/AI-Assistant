# Copilot Instructions (AI-Assistant)

## Project Guidelines
- Project purpose: **AI-Assistant** — smart file version history assistant (Git-based in-place tracking, WikiLLM, temporal graph), multilingual knowledge base (SQLite + FAISS + Obsidian Vault in `ru`, `he`, `en`, `uk`), and personal user assistant (Gmail, Calendar, Drive, Contacts, Document Categorizer).
- Documentation, docstrings, comments, and `README.md` files MUST be written strictly in **Russian**.
- Always follow `.ai/instructions/README.md`, `GEMINI.md`, `.ai/instructions/standards/ENGINEERING.md`, and `.ai/instructions/standards/WEBGUI.md`.
- Update the `Updated: YYYY-MM-DD HH:MM:SS` timestamp in the header of every modified file.
- Never hardcode UI strings (use `locales/*.json` i18n) or colors/styles (use theme CSS variables `var(--...)` and `ui-badge`).
- All modals must be `90vw × 90vh` (§ 5.4 of `WEBGUI.md`), and all form inputs in RTL languages must read right-to-left (§ 5.5 of `WEBGUI.md`).
