"""Find ATS board tokens by company name and append them to companies.csv.

    python discover.py "Figma" "Notion" "Ramp"

Slugifies each name, probes all three ATS APIs, keeps whatever answers.
"""
import csv
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import ats

CSV_PATH = os.path.join(os.path.dirname(__file__), "companies.csv")


def slugs(name):
    """'Match Group' -> ['matchgroup', 'match-group']. Both conventions are in use."""
    base = re.sub(r"[^a-z0-9\s-]", "", name.lower()).strip()
    joined = re.sub(r"[\s-]+", "", base)
    hyphen = re.sub(r"[\s-]+", "-", base)
    return [s for s in dict.fromkeys([joined, hyphen]) if s]


def existing():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return {(r["ats"], r["token"]) for r in csv.DictReader(f)}


def find(session, name):
    """First (ats, token, count) that responds, else None."""
    for token in slugs(name):
        for which in ("greenhouse", "ashby", "lever"):
            n = ats.probe(session, which, token)
            if n:  # exists AND has at least one posting
                return which, token, n
    return None


def main(names):
    if not names:
        print(__doc__)
        return 1
    session = ats.make_session()
    have = existing()
    found, rows = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, hit in zip(names, pool.map(lambda n: find(session, n), names)):
            if not hit:
                print(f"  {name:24} -- no public board found")
                continue
            which, token, n = hit
            mark = "already have" if (which, token) in have else "added"
            print(f"  {name:24} -> {which:10} {token:22} {n:4} jobs  ({mark})")
            if (which, token) not in have:
                rows.append({"ats": which, "token": token, "company": name})
                found.append(name)

    if rows:
        new_file = not os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ats", "token", "company"])
            if new_file:
                w.writeheader()
            w.writerows(rows)
    print(f"\nappended {len(rows)} row(s) to companies.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
