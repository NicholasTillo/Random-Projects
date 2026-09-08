"""Print the scraped feed in the terminal.  python show.py [filter]

Exists because the only other viewer is the Next.js component, and quoting an
f-string through PowerShell -c is its own small nightmare.
"""
import json
import sys
from pathlib import Path

feed = Path(__file__).parent / "out" / "jobs.json"
if not feed.exists():
    sys.exit("No out/jobs.json yet -- run: python scrape.py")

d = json.loads(feed.read_text(encoding="utf-8"))
needle = " ".join(sys.argv[1:]).lower()
jobs = [j for j in d["jobs"] if not needle
        or needle in f"{j['title']} {j['company']} {j['location']} {' '.join(j['tags'])}".lower()]

print(f"{len(jobs)} of {d['count']} roles | {d['boards']} boards | updated {d['generated_at']}\n")
for j in jobs:
    flag = "NEW" if j["is_new"] else "   "
    line = (f"{flag} {j['posted_at'] or '??':10} {j['company'][:16]:16} "
            f"{j['title'][:52]:52} {','.join(j['tags'])[:24]:24} {j['url']}")
    # Windows terminals are not always UTF-8 and job titles love em-dashes
    print(line.encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8"))
