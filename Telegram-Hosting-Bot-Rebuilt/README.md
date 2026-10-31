# Telegram Hosting Manager Pro — rebuilt

**Stack:** Python 3.11+, `python-telegram-bot`, SQLite, Docker. No `aiogram`; no Fernet; no `FERNET_KEY`.

## Features
- `.py` / `.zip` uploads, archive path/symlink checks, file and expansion size limits.
- Heuristic Python scanner with syntax checks and suspicious-pattern flags.
- Manual owner approval before any uploaded project starts.
- Docker CPU, memory, PID, read-only filesystem, non-root user, dropped capabilities, no-new-privileges.
- Admin review, start/stop, container logs, ban/unban, owner notifications and audit log.
- Per-user project limit and SQLite database.

## Install (Ubuntu/Debian VPS)
1. Install Docker Engine and Python 3.11+ on a dedicated, updated VPS.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cp .env.example .env`
5. Set `BOT_TOKEN` and numeric `ADMIN_IDS` in `.env`.
6. `python main.py`

## Admin commands
`/admin`, `/ban USER_ID`, `/unban USER_ID`.

## Token storage
Fernet and `FERNET_KEY` have been removed. Project bot tokens are stored as text in SQLite; the application attempts to set the database file to mode `0600`. This is less secure than encryption. Protect the database, host account and backups. Deleting the Telegram message containing a token is best-effort only. Revoke any exposed token using BotFather.

## Security notes
Static scanning is not antivirus and cannot prove a program is safe. Review source manually. Docker limits reduce risk but are not a perfect security boundary. Do not run this service on a machine with sensitive workloads, do not mount Docker's socket into hosted containers, and do not install user-supplied dependencies automatically. Use a dedicated VPS, firewall, updates, monitoring, and disk quotas.
