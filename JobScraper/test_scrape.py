"""Runnable check: python test_scrape.py

Covers the things that actually broke or would break silently -- per-ATS schema
quirks, the word-boundary intern match, and the first_seen diff.
"""
import ats
import scrape


class FakeResp:
    def __init__(self, payload):
        self._p = payload
        self.ok = True
        self.status_code = 200

    def json(self):
        return self._p

    def raise_for_status(self):
        pass


class FakeSession:
    """Returns a canned payload regardless of URL."""
    def __init__(self, payload):
        self.payload = payload

    def get(self, *a, **kw):
        return FakeResp(self.payload)


def test_lever_schema():
    # Lever: title lives in 'text', createdAt is epoch MILLIseconds.
    s = FakeSession([{
        "id": "abc", "text": "Software Engineer Intern",
        "categories": {"location": "NYC"}, "createdAt": 1711403416463,
        "hostedUrl": "https://jobs.lever.co/x/abc", "descriptionPlain": "we use python",
    }])
    j = ats.fetch_lever(s, "x", "X")[0]
    assert j["title"] == "Software Engineer Intern", j
    assert j["posted_at"] == "2024-03-25", j["posted_at"]  # ms, not seconds
    assert j["key"] == "lever:x:abc"


def test_greenhouse_unescapes_html():
    s = FakeSession({"jobs": [{
        "id": 1, "title": "Data Intern", "location": {"name": "Remote"},
        "absolute_url": "https://x/1", "first_published": "2026-09-04T14:12:20-04:00",
        "content": "&lt;p&gt;We use &lt;b&gt;Python&lt;/b&gt; &amp;amp; Go&lt;/p&gt;",
    }]})
    j = ats.fetch_greenhouse(s, "x", "X")[0]
    assert "<" not in j["text"] and "&lt;" not in j["text"], j["text"]
    assert "Python" in j["text"] and "&" in j["text"], j["text"]
    assert j["posted_at"] == "2026-09-04"


def test_ashby_skips_unlisted():
    s = FakeSession({"jobs": [
        {"id": "a", "title": "Intern", "isListed": False, "publishedAt": "2026-04-07T17:12:35.753+00:00"},
        {"id": "b", "title": "Intern", "isListed": True, "publishedAt": "2026-04-07T17:12:35.753+00:00",
         "jobUrl": "https://x/b", "location": "SF", "descriptionPlain": "text"},
    ]})
    jobs = ats.fetch_ashby(s, "x", "X")
    assert [j["key"] for j in jobs] == ["ashby:x:b"], jobs


def test_intern_word_boundary():
    cfg = scrape.load_config()
    def tags(title):
        return scrape.classify({"title": title, "text": ""}, cfg)
    assert "internship" in tags("Software Engineer Intern")
    assert "internship" in tags("2027 Summer Internship - Backend")
    assert "co-op" in tags("Engineering Co-Op (Fall)")
    # the false positive that makes naive substring matching useless:
    assert tags("Internal Audit Analyst") == [], tags("Internal Audit Analyst")
    assert tags("International Tax Lead") == [], tags("International Tax Lead")
    # exclusions win over a keyword hit
    assert tags("Senior Backend Engineer") == []
    assert tags("University Recruiter") == []


def test_keyword_needs_title_or_repeated_body_use():
    """One passing mention in a long description is not a match -- that flooded the
    feed with marketing roles whose boilerplate happened to say 'backend' once."""
    cfg = scrape.load_config()
    cfg["keyword_only_matches"] = True  # judge keywords on their own here

    once = {"title": "Marketing Coordinator", "text": "we support the backend team"}
    assert scrape.classify(once, cfg) == []

    twice = {"title": "Research Assistant",
             "text": "apply machine   learning daily; machine learning is core"}
    assert "machine learning" in scrape.classify(twice, cfg)  # also checks irregular spacing

    in_title = {"title": "Python Developer", "text": ""}
    assert "python" in scrape.classify(in_title, cfg)


def test_keywords_do_not_widen_feed_by_default():
    cfg = scrape.load_config()
    assert cfg["keyword_only_matches"] is False, "default must stay narrow"
    kw_only = {"title": "Staff Accountant", "text": "python python python"}
    assert scrape.classify(kw_only, cfg) == []
    # ...but they still tag a genuine internship, so the site can filter on them
    both = {"title": "Software Engineer Intern", "text": "python python"}
    tags = scrape.classify(both, cfg)
    assert "internship" in tags and "python" in tags, tags


def test_first_seen_is_stable():
    jobs = [{"key": "a"}, {"key": "b"}]
    state = scrape.apply_seen(jobs, {"a": "2026-01-01"}, today="2026-09-07")
    a, b = jobs
    assert a["is_new"] is False and a["first_seen"] == "2026-01-01"
    assert b["is_new"] is True and b["first_seen"] == "2026-09-07"
    # a delisted-but-recent posting stays remembered so it is not "new" if it returns
    state2 = scrape.apply_seen([], {"c": "2026-09-01"}, today="2026-09-07")
    assert state2 == {"c": "2026-09-01"}
    # ...but an ancient one is pruned
    assert scrape.apply_seen([], {"c": "2020-01-01"}, today="2026-09-07") == {}
    assert state["b"] == "2026-09-07"


def test_age_filter():
    assert scrape.too_old({"posted_at": "2026-01-01"}, "2026-08-01") is True
    assert scrape.too_old({"posted_at": "2026-09-01"}, "2026-08-01") is False
    assert scrape.too_old({"posted_at": None}, "2026-08-01") is False  # unknown != stale


def test_snippet_centres_on_match():
    pat = [scrape.phrase_re("python")]
    text = "x" * 500 + " python " + "y" * 500
    out = scrape.snippet(text, pat, 300)
    assert "python" in out and out.startswith("...") and out.endswith("...")
    assert len(out) <= 310, len(out)
    assert scrape.snippet("", pat, 300) == ""


def test_location_filter():
    pats = [scrape.phrase_re(x) for x in ("Canada", "Toronto", "Ontario", "Vancouver")]

    def ok(**job):
        return scrape.location_ok(job, pats)

    assert ok(locations=["Toronto, Ontario"])
    assert ok(locations=["Toronto"])
    assert ok(locations=["CA-ON-Toronto"])
    # the case that motivated capturing secondary locations at all
    assert ok(locations=["New York, NY (HQ)", "Remote (Canada)"])
    assert not ok(locations=["Shanghai"])
    assert not ok(locations=["Hong Kong; Shanghai"])
    # 'CA' is California far more often than Canada -- must not match on it
    assert not ok(locations=["San Francisco, CA"])
    assert not ok(locations=["San Mateo, CA, United States"])
    # word boundaries: 'Ontario' must not fire on 'London', which contains 'on' twice
    assert not ok(locations=["London"])
    assert not ok(locations=["GB-London"])
    # falls back to the primary string, and an empty filter means anywhere
    assert scrape.location_ok({"location": "Toronto"}, pats)
    assert scrape.location_ok({"locations": ["Shanghai"]}, [])


def test_gui_config_roundtrip(tmp=None):
    """The GUI rewrites config.toml wholesale, so a serialization bug silently
    destroys the user's filters. Round-trip it, quotes and backslashes included."""
    import tempfile
    import tomllib
    from pathlib import Path

    import gui

    cfg = {
        "max_age_days": 30,
        "snippet_chars": 250,
        "match_internships": False,
        "keyword_only_matches": True,
        "keywords": ['say "hi"', "back\\slash", "machine learning", "   "],
        "exclude": ["senior", "staff"],
    }
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.toml"
        gui.write_config(cfg, p)
        text = p.read_text(encoding="utf-8")
        got = tomllib.loads(text)
        # scrape.py must be able to consume what the GUI writes
        assert scrape.load_config(p)["keyword_only_matches"] is True

    assert got["max_age_days"] == 30 and got["snippet_chars"] == 250
    assert got["match_internships"] is False and got["keyword_only_matches"] is True
    assert got["keywords"] == ['say "hi"', "back\\slash", "machine learning"], got["keywords"]
    assert got["exclude"] == ["senior", "staff"]
    assert "# Filtering rules" in text, "comments must survive a GUI save"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
