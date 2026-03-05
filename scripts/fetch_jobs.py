"""
RemotePulse Cloud — fetch_jobs.py
Scrapes remote jobs using JobSpy and saves them to Supabase database.
Runs daily via GitHub Actions (free).
"""

import os
import json
import datetime
import time
import requests

# ── CONFIG (set these as GitHub Secrets) ────────────────────────
SUPABASE_URL    = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY    = os.environ.get("SUPABASE_ANON_KEY", "")
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")

SEARCH_TERMS = [
    "remote software engineer",
    "remote web developer",
    "remote python developer",
    "remote react developer",
    "remote data analyst",
    "remote product manager",
    "remote UI UX designer",
    "remote devops engineer",
]

SITES      = ["indeed", "linkedin", "zip_recruiter", "glassdoor"]
HOURS_OLD  = 24
RESULTS    = 8   # per search term = ~30-60 total after dedup
# ────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

# ── SUPABASE HELPERS ─────────────────────────────────────────────
def supabase_request(method, endpoint, data=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    r = requests.request(method, url, headers=headers, json=data, timeout=15)
    return r

def save_jobs_to_supabase(jobs):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("⚠ No Supabase credentials — saving to jobs.json locally")
        with open("jobs.json", "w") as f:
            json.dump(jobs, f, indent=2)
        return

    # Upsert jobs (insert or update if same url)
    log(f"Saving {len(jobs)} jobs to Supabase...")
    chunk_size = 50
    saved = 0
    for i in range(0, len(jobs), chunk_size):
        chunk = jobs[i:i+chunk_size]
        r = supabase_request("POST", "jobs?on_conflict=url", chunk)
        if r.status_code in [200, 201]:
            saved += len(chunk)
        else:
            log(f"  ⚠ Supabase error: {r.status_code} — {r.text[:200]}")
    log(f"✅ Saved {saved} jobs to Supabase")

def ping_supabase():
    """Keep Supabase project alive (prevents 7-day pause)"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    r = supabase_request("GET", "jobs?limit=1&select=id")
    log(f"Supabase ping: {'OK' if r.status_code == 200 else 'failed'}")

# ── TELEGRAM NOTIFICATION ────────────────────────────────────────
def send_telegram(jobs):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log("No Telegram config — skipping notification")
        return

    top5 = jobs[:5]
    lines = [f"⚡ *RemotePulse — {len(jobs)} new remote jobs today!*\n"]
    for j in top5:
        salary = f" · {j['salary']}" if j.get('salary') else ""
        lines.append(f"💼 *{j['title']}*")
        lines.append(f"🏢 {j['company']}{salary}")
        lines.append(f"🔗 [Apply]({j['url']})\n")
    lines.append(f"🌐 [View all jobs on dashboard]({os.environ.get('DASHBOARD_URL','#')})")

    msg = "\n".join(lines)
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True},
        timeout=10
    )
    if r.status_code == 200:
        log("✅ Telegram notification sent!")
    else:
        log(f"⚠ Telegram failed: {r.text[:200]}")

# ── MAIN FETCH ───────────────────────────────────────────────────
def fetch_jobs():
    log("="*50)
    log("RemotePulse: Starting daily job fetch...")
    log(f"Sites: {', '.join(SITES)}")
    log(f"Search terms: {len(SEARCH_TERMS)}")

    try:
        from jobspy import scrape_jobs
    except ImportError:
        log("ERROR: python-jobspy not installed.")
        raise

    all_jobs = []
    seen_urls = set()

    for term in SEARCH_TERMS:
        log(f"Searching: '{term}'...")
        try:
            df = scrape_jobs(
                site_name=SITES,
                search_term=term,
                results_wanted=RESULTS,
                hours_old=HOURS_OLD,
                is_remote=True,
                country_indeed="worldwide",
            )

            if df is None or len(df) == 0:
                log(f"  → 0 results")
                continue

            count = 0
            for _, row in df.iterrows():
                url = str(row.get("job_url", "")).strip()
                if not url or url in seen_urls or url == "nan":
                    continue
                seen_urls.add(url)

                salary = ""
                try:
                    mn = row.get("min_amount")
                    mx = row.get("max_amount")
                    if mn and str(mn) not in ["nan","None","0"]:
                        salary = f"${int(float(mn)):,}–${int(float(mx or mn)):,}/yr"
                except:
                    pass

                job = {
                    "title":       str(row.get("title","")).strip() or "Unknown Role",
                    "company":     str(row.get("company","")).strip() or "Unknown",
                    "location":    str(row.get("location","Worldwide")).strip(),
                    "site":        str(row.get("site","")).strip().capitalize(),
                    "salary":      salary,
                    "job_type":    str(row.get("job_type","")).replace("JobType.","").replace("_"," ").title(),
                    "url":         url,
                    "date_posted": str(row.get("date_posted",""))[:10],
                    "description": str(row.get("description",""))[:500].strip() if row.get("description") else "",
                    "search_term": term,
                    "fetched_at":  datetime.datetime.utcnow().isoformat(),
                }
                all_jobs.append(job)
                count += 1

            log(f"  → {count} unique jobs found")
            time.sleep(4)  # polite delay

        except Exception as e:
            log(f"  → Error on '{term}': {e}")
            continue

    # Deduplicate by url
    seen = set()
    unique_jobs = []
    for j in all_jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            unique_jobs.append(j)

    log(f"\nTotal unique jobs: {len(unique_jobs)}")

    if unique_jobs:
        save_jobs_to_supabase(unique_jobs)
        send_telegram(unique_jobs)
        ping_supabase()

    log("✅ Done!")
    return len(unique_jobs)

if __name__ == "__main__":
    fetch_jobs()
