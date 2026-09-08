# ATS Job Scraper

Aggregates internship and new-grad postings straight from company applicant-tracking
systems, hours after they go up and long before they reach the big job boards.

Greenhouse, Lever and Ashby all serve their job boards as **anonymous public JSON**.
What they don't offer is search across companies — you query one board at a time —
which is why aggregators mostly ignore them, and why postings surface here first.

Currently watching **67 boards**, scanning ~14,500 live postings per run in **26 seconds**.

## How it works

```
GitHub Actions (cron, every 6h)
  companies.csv ──> 3 ATS adapters ──> normalize ──> filter
                     (8 threads)                       │
  previous seen.json ──────────────────────────────────┤ diff → first_seen / is_new
                                                       ▼
                                          out/jobs.json + out/seen.json
                                                       │
                                  force-push to `jobs-data` branch (no history)
                                                       ▼
                                    Next.js RSC fetch → <JobBoard /> → client filtering
```

No server, no database, no hosting bill. `seen.json` is the database.

### The constraint that shaped the design

Stripe's Greenhouse board alone is **4.78 MB** with descriptions attached (619 postings;
`content=true` inflates the payload ~12x). Across 67 boards that is far too much to ship
to a browser, and committing it four times a day would add ~90 MB of git history a year.

So descriptions are fetched, matched, and **discarded in CI**. Only matches reach the
published feed, each with a 300-character snippet — 89 roles, 65 KB.

The trade-off, stated plainly: the search box on the site can only match what was
published (title, company, location, snippet, tags). Deep description matching is driven
by the keyword list in `config.toml` and happens during the scrape.

### Filtering

Internship patterns match the **title only**. Matching them against descriptions is
useless — plenty of senior roles mention "our interns" in the boilerplate. Word
boundaries do real work here: `\bintern\b` accepts *Software Engineer Intern* and
rejects *Internal Audit* and *International Tax*.

Keywords need to appear in the title or be used **at least twice** in the description.
An early version accepted a single mention and returned 917 "matches", including a
Marketing Operations Coordinator whose boilerplate said "backend" once. Requiring
repeat usage cut that to 89 genuine roles.

By default keywords *narrow* the internship feed rather than widening it — they tag
results so the site can filter on them. Set `keyword_only_matches = true` for the wide
net, and expect roughly 10x the volume.

## Use it

```bash
pip install requests            # the only dependency
python gui.py                   # desktop control panel: edit filters, run, browse results
```

Everything the GUI does is also available headless:

```bash
python test_scrape.py           # 10 checks, no framework
python scrape.py                # → out/jobs.json
python show.py intern           # read the results in the terminal
```

Add companies without looking up board tokens by hand:

```bash
$ python discover.py "Figma" "Notion" "Anduril Industries"
  Figma                -> greenhouse figma              157 jobs  (added)
  Notion               -> ashby      notion             132 jobs  (added)
  Anduril Industries   -> greenhouse andurilindustries 2212 jobs  (added)
```

Tune `config.toml` — keywords, locations, exclusions, `max_age_days` — then re-run.
No code changes.

## Desktop control panel

`python gui.py` — one window, no dependencies beyond the standard library.

Left: the filters from `config.toml` as real widgets (max age, the two matching modes,
keywords, exclusions). **Save && Run scrape** writes the config and runs `scrape.py` as a
subprocess, so a hang or crash in the scrape cannot take the UI with it; output streams
back through a queue because tkinter is not thread-safe.

Right: the results, filterable and sortable by any column, with new postings highlighted.
Double-click opens the posting in your browser.

Saving rewrites `config.toml` wholesale and re-emits its explanatory comments, so the
file keeps documenting itself after you touch a checkbox.

## Website integration

`web/JobBoard.tsx` is a Next.js server component; `web/JobList.tsx` is its client-side
filtering child. Copy both in, render `<JobBoard />`, done. It fetches with
`revalidate: 3600`, so the page is server-rendered and the feed never touches the
browser's origin check — though the feed does send `Access-Control-Allow-Origin: *`
if you'd rather fetch it client-side.

## Layout

| Path | |
|---|---|
| `ats.py` | Endpoint definitions + one adapter per ATS, normalizing to a shared schema |
| `scrape.py` | Concurrent fetch, filtering, first-seen diffing, feed output |
| `discover.py` | Board-token finder |
| `show.py` | Prints the feed in the terminal: `python show.py intern` |
| `gui.py` | tkinter control panel — edit filters, run the scrape, open postings |
| `companies.csv` | `ats,token,company` — the watch list, and the coverage |
| `config.toml` | Filter rules |
| `../.github/workflows/scrape-jobs.yml` | The 6-hourly run (workflows must live at the repo root) |

### Per-ATS quirks, the hard way

- **Lever** calls the job title `text`, not `title`, and `createdAt` is epoch
  *milliseconds*.
- **Greenhouse** returns HTML-escaped HTML in `content`, and only one location string.
- **Ashby** has the cleanest schema (`isRemote`, `workplaceType`, `descriptionPlain`
  free of charge) but includes unlisted postings you have to filter on `isListed`.

### Locations

Location strings are a mess across boards — one run produced `Toronto`,
`Toronto, Ontario`, `San Francisco, CA`, `San Francisco - SF9`, `US-WA-Bellevue`,
`GB-London` and `Hong Kong; Shanghai`. So `locations` is word-boundary matched against
*every* location a board reports, and you should list cities **and** the country.

Two things this deliberately does not do:

- **No 2-letter codes.** `CA` is California on almost every US board and Canada on
  Lever. There is no way to disambiguate them downstream, so country codes are dropped
  at the adapter.
- **`Remote` is not implied.** A bare "Remote" usually means US-remote. Ashby is the
  only ATS that names secondary offices explicitly, so `Remote (Canada)` on a
  New-York-primary role is caught via its `secondaryLocations` — the other two boards
  simply don't publish that.

## Known limits

- A board is only covered if it's in `companies.csv`. That list is the product, and it
  is the binding constraint once you filter by location — a country filter can only
  return what the watch list covers.
- Token guessing works on ~70% of names; the rest use a token that isn't their slug
  (Anduril is `andurilindustries`) and need a manual row.
- First run flags every posting as new — there's no prior state to diff against.
- Companies on Workday, SmartRecruiters or a custom board aren't supported. Both have
  public APIs; each is one adapter in `ats.py` plus a row in `FETCHERS`.
