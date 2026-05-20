# n8n-job-hunter

Automated job hunting pipeline for Staff/Senior TPM roles. Scrapes Indeed and LinkedIn every 12 hours, scores fitment against your profile using Claude Haiku, and emails an HTML digest of matching roles (≥72% fitment).

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/YOUR_USERNAME/n8n-job-hunter.git
cd n8n-job-hunter
./n8n.sh setup

# 2. Edit .env with your real credentials
vim .env

# 3. Import the workflow
./n8n.sh import

# 4. Open n8n and activate the workflow
open http://localhost:5678
```

## Prerequisites

- Docker Desktop (macOS)
- Anthropic API key (Claude Haiku)
- SMTP credentials (Outlook app password)

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `N8N_USER` | n8n login email |
| `N8N_PASSWORD` | n8n login password |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Haiku |
| `SMTP_HOST` | SMTP server (default: smtp-mail.outlook.com) |
| `SMTP_PORT` | SMTP port (default: 587) |
| `SMTP_USER` | Your email address |
| `SMTP_PASSWORD` | App password (not your regular password) |
| `SMTP_FROM` | Sender email |
| `SMTP_TO` | Recipient email for digests |

## Management Commands

```bash
./n8n.sh setup     # First-time setup
./n8n.sh start     # Start container
./n8n.sh stop      # Stop container
./n8n.sh restart   # Restart container
./n8n.sh logs      # Tail logs
./n8n.sh status    # Container status
./n8n.sh update    # Pull latest n8n image
./n8n.sh import    # Import workflow JSON
./n8n.sh clean     # Remove all data (destructive)
./n8n.sh shell     # Shell into container
```

## Standalone Python Script

Run without n8n:

```bash
cd scripts
python3 job_hunter.py
```

Requires Python 3.10+ (uses only stdlib). Reads `.env` from project root.

## Pipeline Flow

1. **Trigger** — Every 12 hours (or manual)
2. **Scrape** — Indeed + LinkedIn for TPM/PM roles in India
3. **Fetch JD** — Get full job description text
4. **Score** — Claude Haiku scores fitment (0-100)
5. **Filter** — Keep only ≥72% matches
6. **Deduplicate** — Skip already-seen jobs (idempotent)
7. **Digest** — Build HTML table with score, matches, gaps, resume recommendation
8. **Email** — Send via SMTP

## Resource Limits

Docker container is capped at 1 CPU and 1GB RAM to prevent resource exhaustion.

## Security

- No secrets in committed files
- All credentials via `.env` (gitignored)
- n8n credentials stored encrypted in Docker volume
