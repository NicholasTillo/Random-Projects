"""Adapters for public ATS job-board APIs.

Greenhouse, Lever and Ashby all serve their company job boards as anonymous JSON.
No auth, no API key. There is no cross-company search endpoint on any of them --
you ask one board at a time, which is why companies.csv exists.

Every adapter returns the same normalized dict so the rest of the code never has
to care which ATS a posting came from.
"""
import html
import re
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

UA = "JobScraper/1.0 (+https://github.com/NicholasTillo/JobScraper)"

# {token} boards. Greenhouse's content=true roughly 12x's the payload (Stripe: 386KB -> 4.8MB),
# so it is only requested when the config actually has description keywords to match.
ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true",
}

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def make_session():
    """Session with backoff on the failure modes these APIs actually exhibit."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.headers["User-Agent"] = UA
    return s


def plain(s):
    """HTML -> matchable text.

    ponytail: regex tag-strip, not a parser. Adequate for keyword matching since we
    never render this. Swap in html.parser if matches start picking up markup.
    """
    return _WS.sub(" ", _TAGS.sub(" ", html.unescape(s or ""))).strip()


def _iso_date(s):
    """'2026-09-04T14:12:20-04:00' / '...753+00:00' / '...Z' -> '2026-09-04'."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _ms_date(ms):
    """Lever hands out epoch MILLIseconds, not seconds."""
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).date().isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _job(ats, token, company, jid, title, location, url, posted_at, text, locations=None):
    """`location` is the primary string for display; `locations` is everything we know,
    including secondary/remote offices, and is what location filtering matches against.

    Deliberately excludes 2-letter country codes: 'CA' means California on a US board
    and Canada on Lever's, and there is no way to tell them apart downstream.
    """
    seen, all_locs = set(), []
    for loc in [location] + list(locations or []):
        loc = (loc or "").strip()
        if loc and loc.lower() not in seen:
            seen.add(loc.lower())
            all_locs.append(loc)
    return {
        "key": f"{ats}:{token}:{jid}",
        "ats": ats,
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "locations": all_locs,
        "url": url or "",
        "posted_at": posted_at,
        "text": text or "",  # dropped before publishing; matching only
    }


def fetch_greenhouse(session, token, company, want_text=True):
    url = ENDPOINTS["greenhouse"].format(token=token)
    r = session.get(url, params={"content": "true" if want_text else "false"}, timeout=90)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append(_job(
            "greenhouse", token, company, j.get("id"),
            title=j.get("title"),
            location=(j.get("location") or {}).get("name"),
            url=j.get("absolute_url"),
            posted_at=_iso_date(j.get("first_published") or j.get("updated_at")),
            text=plain(j.get("content")) if want_text else "",
        ))
    return jobs


def fetch_lever(session, token, company, want_text=True):
    r = session.get(ENDPOINTS["lever"].format(token=token), timeout=90)
    r.raise_for_status()
    jobs = []
    for j in r.json():  # flat array, not wrapped
        cats = j.get("categories") or {}
        jobs.append(_job(
            "lever", token, company, j.get("id"),
            title=j.get("text"),  # NOT j["title"] -- Lever calls it 'text'
            location=cats.get("location"),
            locations=cats.get("allLocations") or [],
            url=j.get("hostedUrl") or j.get("applyUrl"),
            posted_at=_ms_date(j.get("createdAt")),
            text=" ".join(filter(None, [j.get("descriptionPlain"), j.get("additionalPlain")])),
        ))
    return jobs


def fetch_ashby(session, token, company, want_text=True):
    r = session.get(ENDPOINTS["ashby"].format(token=token), timeout=90)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        if not j.get("isListed", True):
            continue
        # Ashby is the only one that spells out remote/secondary offices -- a role whose
        # primary location is New York may still be open as "Remote (Canada)".
        extra = []
        for sec in [j] + list(j.get("secondaryLocations") or []):
            extra.append(sec.get("location"))
            country = ((sec.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
            if country and len(country) > 2:  # full names only; 'CA' is ambiguous
                extra.append(country)
        if j.get("isRemote"):
            extra.append("Remote")
        jobs.append(_job(
            "ashby", token, company, j.get("id"),
            title=j.get("title"),
            location=j.get("location"),
            locations=extra,
            url=j.get("jobUrl") or j.get("applyUrl"),
            posted_at=_iso_date(j.get("publishedAt")),
            text=j.get("descriptionPlain"),
        ))
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


def probe(session, ats, token):
    """Does this board token exist on this ATS? -> job count, or None."""
    try:
        jobs = FETCHERS[ats](session, token, token, want_text=False)
    except (requests.RequestException, ValueError, KeyError):
        return None
    return len(jobs)
