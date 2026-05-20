#!/usr/bin/env python3
"""Standalone job hunter pipeline - scrapes, scores, and emails digest."""

import os
import json
import hashlib
import smtplib
import time
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote_plus

# Load .env file
ENV_PATH = Path(__file__).parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp-mail.outlook.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_TO = os.environ.get("SMTP_TO", "")
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

PROFILE = """Rahul Goel - Staff TPM, 20 years experience.
Recent: Amazon India - $165M AWS portfolio, GDPR compliance, GenAI delivery (AskGenie 88% autonomous resolution, Procurement Advisor $2.3M ROI), $5.3B Capital Planning, $8M FinOps savings, EagleEye observability (Datadog, Prometheus), 10+ Senior Engineers managed.
Prior: Deloitte Digital 7 years 45-member teams, Marketo Engage ML automation 2.5x ROI.
Tech: AWS, Bedrock Agents, RAG, LLMOps, LangChain, OAuth 2.0, GDPR, SOC2, Datadog, Terraform, Kubernetes, Docker, Java, Python, SQL, Agile, SAFe, OKR, JIRA.
Certs: PMP, AWS Solutions Architect, Google Cloud Gen AI Leader."""

QUERIES = [
    "Staff TPM India",
    "Senior TPM India",
    "Engineering Program Manager India",
    "GenAI Program Manager India",
    "Principal Program Manager India",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch URL content."""
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return ""


def scrape_jobs() -> list[dict]:
    """Scrape Indeed and LinkedIn for matching roles."""
    import re
    jobs = []
    seen = set()

    for query in QUERIES:
        # Indeed
        url = f"https://www.indeed.co.in/jobs?q={quote_plus(query)}&l=India&sort=date&fromage=1"
        html = fetch_url(url)
        for m in re.finditer(
            r'data-jk="([^"]+)"[\s\S]*?<h2[^>]*>\s*<a[^>]*>\s*<span[^>]*>([^<]+)</span>[\s\S]*?<span[^>]*data-testid="company-name"[^>]*>([^<]+)</span>',
            html,
        ):
            jid = f"indeed_{m.group(1)}"
            if jid not in seen:
                seen.add(jid)
                jobs.append({
                    "id": jid, "source": "indeed", "title": m.group(2).strip(),
                    "company": m.group(3).strip(),
                    "url": f"https://www.indeed.co.in/viewjob?jk={m.group(1)}",
                    "query": query,
                })

        # LinkedIn
        url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}&location=India&f_TPR=r86400"
        html = fetch_url(url)
        for m in re.finditer(
            r'data-entity-urn="urn:li:jobPosting:(\d+)"[\s\S]*?<span[^>]*>([^<]+)</span>[\s\S]*?<h4[^>]*>([^<]+)</h4>',
            html,
        ):
            jid = f"linkedin_{m.group(1)}"
            if jid not in seen:
                seen.add(jid)
                jobs.append({
                    "id": jid, "source": "linkedin", "title": m.group(2).strip(),
                    "company": m.group(3).strip(),
                    "url": f"https://www.linkedin.com/jobs/view/{m.group(1)}",
                    "query": query,
                })

        time.sleep(2)  # Rate limiting

    print(f"[INFO] Scraped {len(jobs)} jobs")
    return jobs


def fetch_jd(job: dict) -> str:
    """Fetch and extract JD text."""
    import re
    html = fetch_url(job["url"])
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text[:3000]


def score_job(job: dict, jd_text: str) -> dict:
    """Score job fitment using Claude Haiku."""
    import urllib.request

    prompt = f"""You are a job fitment scoring engine. Score how well this candidate matches the job.

Candidate Profile:
{PROFILE}

Job:
Title: {job['title']}
Company: {job['company']}
Description: {jd_text}

Respond in EXACTLY this JSON format (no markdown, no explanation):
{{"score": <0-100>, "top_matches": ["match1", "match2", "match3"], "gaps": ["gap1", "gap2"], "resume_version": "<Saviynt-focused if role emphasizes security/compliance/IAM, otherwise Guidewire-focused>"}}"""

    body = json.dumps({
        "model": "claude-3-haiku-20240307",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            result = json.loads(data["content"][0]["text"])
            return {**job, **result, "jd_text": jd_text[:200]}
    except Exception as e:
        print(f"  [WARN] Scoring failed for {job['title']}: {e}")
        return {**job, "score": 0, "top_matches": [], "gaps": ["Scoring failed"], "resume_version": "Guidewire-focused"}


def deduplicate(jobs: list[dict]) -> list[dict]:
    """Remove duplicates against today's saved file."""
    today_file = OUTPUT_DIR / f"jobs_{date.today().isoformat()}.json"
    existing = []
    if today_file.exists():
        existing = json.loads(today_file.read_text())

    existing_ids = {j["id"] for j in existing}
    new_jobs = [j for j in jobs if j["id"] not in existing_ids]
    merged = existing + new_jobs
    today_file.write_text(json.dumps(merged, indent=2))
    print(f"[INFO] Saved {len(new_jobs)} new jobs ({len(merged)} total today)")
    return new_jobs


def build_html(jobs: list[dict]) -> str:
    """Build HTML email digest."""
    if not jobs:
        return "<p>No matching jobs found this run (all below 72% fitment).</p>"

    rows = ""
    for j in sorted(jobs, key=lambda x: x["score"], reverse=True):
        rows += f"""<tr>
            <td style="padding:8px;border:1px solid #ddd;font-weight:bold;color:#1a73e8">{j['score']}%</td>
            <td style="padding:8px;border:1px solid #ddd">{j['company']}</td>
            <td style="padding:8px;border:1px solid #ddd"><a href="{j['url']}">{j['title']}</a></td>
            <td style="padding:8px;border:1px solid #ddd">{', '.join(j.get('top_matches', []))}</td>
            <td style="padding:8px;border:1px solid #ddd;color:#d93025">{', '.join(j.get('gaps', []))}</td>
            <td style="padding:8px;border:1px solid #ddd">{j.get('resume_version', 'Guidewire-focused')}</td>
        </tr>"""

    return f"""<h2 style="color:#1a73e8">🎯 Job Hunter Digest - {datetime.now().strftime('%d/%m/%Y')}</h2>
<p>{len(jobs)} roles matched (≥72% fitment)</p>
<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px">
<tr style="background:#1a73e8;color:white">
    <th style="padding:8px">Score</th><th style="padding:8px">Company</th>
    <th style="padding:8px">Title</th><th style="padding:8px">Top Matches</th>
    <th style="padding:8px">Gaps</th><th style="padding:8px">Resume</th>
</tr>{rows}</table>
<p style="color:#666;font-size:12px">Generated by job_hunter.py | {datetime.now().isoformat()}</p>"""


def send_email(html: str, count: int):
    """Send HTML digest via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[WARN] SMTP not configured, skipping email. HTML saved to outputs/")
        (OUTPUT_DIR / f"digest_{date.today().isoformat()}.html").write_text(html)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 Job Hunter: {count} roles matched - {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = SMTP_FROM
    msg["To"] = SMTP_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print(f"[INFO] Email sent to {SMTP_TO}")


def main():
    print(f"{'='*60}")
    print(f"Job Hunter Pipeline - {datetime.now().isoformat()}")
    print(f"{'='*60}")

    # Scrape
    jobs = scrape_jobs()
    if not jobs:
        print("[INFO] No jobs found, exiting")
        return

    # Fetch JDs and score
    scored = []
    for i, job in enumerate(jobs):
        print(f"  [{i+1}/{len(jobs)}] Scoring: {job['title']} @ {job['company']}")
        jd = fetch_jd(job)
        result = score_job(job, jd)
        scored.append(result)
        time.sleep(1)  # Rate limit Anthropic

    # Filter >= 72%
    matched = [j for j in scored if j["score"] >= 72]
    print(f"[INFO] {len(matched)}/{len(scored)} jobs above 72% fitment")

    # Deduplicate
    new_matches = deduplicate(matched)

    # Build and send digest
    html = build_html(matched)
    send_email(html, len(matched))

    print(f"[DONE] Pipeline complete")


if __name__ == "__main__":
    main()
