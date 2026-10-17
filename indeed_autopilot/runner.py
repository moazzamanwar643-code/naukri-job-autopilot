"""Indeed job discovery and review queue. No authenticated application submission."""
import csv
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

OUT = Path("indeed_autopilot/output")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://in.indeed.com"
QUERIES = [
    ("electrical", "graduate engineer trainee electrical"),
    ("electrical", "junior electrical engineer"),
    ("electrical", "electrical maintenance engineer fresher"),
    ("electrical", "electrical testing commissioning trainee"),
    ("logistics", "logistics analyst"),
    ("logistics", "import export customs analyst"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobResearch/1.0)", "Accept-Language": "en-IN,en;q=0.9"}
BLOCKED = ("captcha", "verify you are human", "unusual traffic", "security check")
EXCLUDE = ("senior manager", "director", "head of ", "principal engineer", "10+ years")
MAX_JOBS = int(os.getenv("MAX_JOBS", "40"))

def fetch_jobs(query):
    url = f"{BASE}/jobs?q={quote_plus(query)}&l=India&fromage=7"
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    lower = response.text.lower()
    if any(marker in lower for marker in BLOCKED):
        raise RuntimeError("Indeed returned a verification or bot-protection page")
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []
    for card in soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard, div.cardOutline"):
        a = card.select_one("h2 a[href], a.jcs-JobTitle[href]")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = urljoin(BASE, a["href"])
        parsed = urlparse(href)
        jid = parse_qs(parsed.query).get("jk", [None])[0] or card.get("data-jk")
        if not jid:
            continue
        company = card.select_one("[data-testid='company-name'], span.companyName")
        place = card.select_one("[data-testid='text-location'], div.companyLocation")
        snippet = card.select_one(".job-snippet, [data-testid='job-snippet']")
        jobs.append({"id": jid, "title": title, "company": company.get_text(" ", strip=True) if company else "",
                     "location": place.get_text(" ", strip=True) if place else "",
                     "description": snippet.get_text(" ", strip=True) if snippet else "",
                     "url": f"{BASE}/viewjob?jk={quote_plus(jid)}"})
    return jobs

def classification(job, track):
    content = (job["title"] + " " + job["description"]).lower()
    if any(word in content for word in EXCLUDE):
        return None
    if track == "electrical" and not any(w in content for w in ("electrical", "maintenance", "commissioning", "testing", "graduate engineer")):
        return None
    if track == "logistics" and not any(w in content for w in ("logistics", "supply chain", "customs", "import", "export", "exim")):
        return None
    return track

def main():
    seen = {}
    errors = []
    for track, query in QUERIES:
        try:
            for job in fetch_jobs(query):
                match = classification(job, track)
                if not match or job["id"] in seen:
                    continue
                job["track"] = match
                job["status"] = "ACTION_REQUIRED"
                job["reason"] = "Review listing, tailor resume and submit application manually"
                seen[job["id"]] = job
                if len(seen) >= MAX_JOBS:
                    break
        except (requests.RequestException, RuntimeError) as exc:
            errors.append(f"{query}: {exc}")
        if len(seen) >= MAX_JOBS:
            break
    jobs = list(seen.values())
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "discovered": len(jobs),
              "submitted": 0, "note": "Discovery only. No applications were submitted.", "errors": errors, "jobs": jobs}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "review_queue.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["track", "title", "company", "location", "url", "status", "reason"])
        writer.writeheader()
        writer.writerows([{k: job[k] for k in writer.fieldnames} for job in jobs])
    summary = [f"Indeed discovery: {len(jobs)} jobs found. 0 applications submitted."]
    if errors:
        summary.append("Some searches failed: " + "; ".join(errors)[:1000])
    if not jobs:
        summary.append("No accessible job cards were returned. This may be because Indeed blocked automated access.")
    message = "\n".join(summary)
    print(message)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": message}, timeout=15).raise_for_status()
        except requests.RequestException as exc:
            print("Telegram notification failed:", exc)
    if not jobs and errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
