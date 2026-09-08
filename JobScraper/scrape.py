"""Poll every board in companies.csv, filter, and publish out/jobs.json.

    python scrape.py

Descriptions are matched here and thrown away. Only matches -- with a short
snippet -- get published, because a single Greenhouse board with descriptions
attached is ~5MB and no browser is going to download 67 of those.
"""
import csv
import json
import os
import re
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ats

HERE = Path(__file__).parent
OUT = HERE / "out"
SEEN_TTL_DAYS = 90  # remember a posting this long after it leaves the board

# Matched against the TITLE ONLY. Descriptions mention "our interns" in boilerplate
# on plenty of senior roles, so matching these against body text is useless.
INTERN_PATTERNS = [
    (re.compile(r"\bintern(ship)?s?\b", re.I), "internship"),
    (re.compile(r"\bco-?ops?\b", re.I), "co-op"),
    (re.compile(r"\bnew[\s-]?grads?\b", re.I), "new-grad"),
    (re.compile(r"\bgraduate\b", re.I), "new-grad"),
    (re.compile(r"\bclass of 20\d\d\b", re.I), "new-grad"),
    (re.compile(r"\buniversity\b", re.I), "university"),
    (re.compile(r"\bcampus\b", re.I), "campus"),
    (re.compile(r"\bearly[\s-]career\b", re.I), "early-career"),
    (re.compile(r"\b(summer|fall|winter|spring)\s+20\d\d\b", re.I), "seasonal"),
]


def phrase_re(kw):
    """Literal phrase, word-boundaried, tolerant of irregular whitespace.

    Escape per word rather than escaping the whole phrase: re.escape() escapes a
    space to '\\ ', so substituting on ' ' afterwards leaves a literal backslash in
    the pattern and any multi-word keyword silently matches nothing.
    """
    parts = [re.escape(w) for w in kw.split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.I)


def load_config(path=None):
    with open(path or HERE / "config.toml", "rb") as f:
        cfg = tomllib.load(f)
    cfg["keyword_re"] = [(phrase_re(k), k) for k in cfg.get("keywords", []) if k.strip()]
    cfg["exclude_re"] = [phrase_re(k) for k in cfg.get("exclude", []) if k.strip()]
    cfg["location_re"] = [phrase_re(k) for k in cfg.get("locations", []) if k.strip()]
    cfg.setdefault("max_age_days", 45)
    cfg.setdefault("snippet_chars", 300)
    cfg.setdefault("match_internships", True)
    cfg.setdefault("keyword_only_matches", False)
    return cfg


def load_companies(path=None):
    with open(path or HERE / "companies.csv", newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("token")]


# A keyword mentioned once in a 5000-word description means nothing -- job posts name
# every technology in the building. Require the title, or repeated use in the body.
MIN_BODY_HITS = 2


def classify(job, cfg):
    """-> list of tags. Empty means the posting does not match and is dropped."""
    title = job["title"]
    if any(p.search(title) for p in cfg["exclude_re"]):
        return []

    intern_tags = []
    if cfg["match_internships"]:
        for pat, tag in INTERN_PATTERNS:
            if pat.search(title) and tag not in intern_tags:
                intern_tags.append(tag)

    text = job.get("text", "")
    kw_tags = [kw for pat, kw in cfg["keyword_re"]
               if pat.search(title) or len(pat.findall(text)) >= MIN_BODY_HITS]

    # Keywords normally *narrow* the internship feed rather than widening it: without
    # this, "python" appearing in any description drags in every marketing coordinator
    # at every company. Set keyword_only_matches=true to cast the wide net instead.
    if not intern_tags and not (kw_tags and cfg["keyword_only_matches"]):
        return []
    return intern_tags + [k for k in kw_tags if k not in intern_tags]


def snippet(text, patterns, n):
    """n chars of context centred on the first match, so the UI has something to show."""
    if not text:
        return ""
    pos = min((m.start() for m in filter(None, (p.search(text) for p in patterns))), default=-1)
    if pos < 0:
        return text[:n].strip()
    start = max(0, pos - n // 2)
    body = text[start:start + n].strip()
    return ("..." if start else "") + body + ("..." if start + n < len(text) else "")


def location_ok(job, patterns):
    """Empty pattern list means anywhere.

    Matched word-boundaried against every location we captured, because these strings
    are wildly inconsistent across boards -- 'Toronto', 'Toronto, Ontario', 'CA-ON-Toronto'
    and 'Hong Kong; Shanghai' all appear in one run. List cities and the country.
    """
    if not patterns:
        return True
    hay = " | ".join(job.get("locations") or [job.get("location", "")])
    return any(p.search(hay) for p in patterns)


def too_old(job, cutoff):
    if not job.get("posted_at"):
        return False  # no date is not evidence of being stale
    return job["posted_at"] < cutoff


def load_seen(session):
    """Previous run's state: local file first, then the published feed."""
    local = OUT / "seen.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    url = os.environ.get("SEEN_URL")
    if url:
        try:
            r = session.get(url, timeout=30)
            if r.ok:
                return r.json()
            print(f"  seen.json: {r.status_code} from SEEN_URL (first run?)")
        except Exception as e:  # noqa: BLE001 - never let state loss kill the run
            print(f"  seen.json: {type(e).__name__} fetching SEEN_URL ({e})")
    return {}


def apply_seen(jobs, seen, today=None):
    """Stamp first_seen/is_new, and return the state to persist."""
    today = today or date.today().isoformat()
    keep_after = (date.fromisoformat(today) - timedelta(days=SEEN_TTL_DAYS)).isoformat()
    state = {}
    for j in jobs:
        j["is_new"] = j["key"] not in seen
        j["first_seen"] = seen.get(j["key"], today)
        state[j["key"]] = j["first_seen"]
    # carry forward postings that dropped off the board, so they are not "new" if they return
    for k, v in seen.items():
        if k not in state and v >= keep_after:
            state[k] = v
    return state


def main():
    cfg = load_config()
    rows = load_companies()
    session = ats.make_session()
    # ponytail: skip the 12x content=true payload when nothing needs description matching
    want_text = bool(cfg["keyword_re"])

    print(f"scraping {len(rows)} boards (descriptions={'on' if want_text else 'off'})")
    raw, failed = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(ats.FETCHERS[r["ats"]], session, r["token"], r["company"], want_text): r
            for r in rows if r["ats"] in ats.FETCHERS
        }
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                raw.extend(fut.result())
            except Exception as e:  # noqa: BLE001 - one dead board must not kill the run
                failed.append(f"{row['ats']}:{row['token']} {type(e).__name__}: {e}")

    cutoff = (date.today() - timedelta(days=cfg["max_age_days"])).isoformat()
    all_pats = [p for p, _ in cfg["keyword_re"]] + [p for p, _ in INTERN_PATTERNS]
    matched = []
    for job in raw:
        if too_old(job, cutoff) or not location_ok(job, cfg["location_re"]):
            continue
        tags = classify(job, cfg)
        if not tags:
            continue
        job["tags"] = tags
        job["snippet"] = snippet(job.pop("text", ""), all_pats, cfg["snippet_chars"])
        job["locations"] = job.get("locations") or []
        matched.append(job)

    seen = load_seen(session)
    state = apply_seen(matched, seen)
    matched.sort(key=lambda j: (j["posted_at"] or "", j["company"]), reverse=True)

    OUT.mkdir(exist_ok=True)
    feed = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boards": len(rows) - len(failed),
        "count": len(matched),
        "jobs": matched,
    }
    (OUT / "jobs.json").write_text(json.dumps(feed, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "seen.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    size = (OUT / "jobs.json").stat().st_size / 1024
    print(f"  {len(raw)} postings scanned -> {len(matched)} matched "
          f"({sum(j['is_new'] for j in matched)} new), {size:.0f}KB")
    for f in failed:
        print(f"  FAILED {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
