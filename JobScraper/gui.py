"""Single-screen desktop front end: edit the filters, run the scrape, read the results.

    python gui.py

tkinter because it ships with Python -- this is a local control panel, not the thing
that goes on the website. The web UI lives in web/.
"""
import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tomllib
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

HERE = Path(__file__).parent
CONFIG = HERE / "config.toml"
FEED = HERE / "out" / "jobs.json"

# Rewritten wholesale on save, so the explanatory comments are re-emitted with it
# rather than being silently eaten the first time you touch a checkbox.
TEMPLATE = """# Filtering rules. Edit here or in gui.py -- no code changes needed.
# These run against FULL job descriptions during the scrape. The search box on the
# website can only match what gets published (title + snippet + tags), so anything
# you want to search deeply has to be a keyword here.

max_age_days = {max_age_days}      # drop postings older than this
snippet_chars = {snippet_chars}    # context shipped per job for the UI

# Internship / new-grad patterns are matched against the TITLE ONLY.
# Matching them against descriptions floods results with senior roles that merely
# mention "our interns" somewhere in the boilerplate.
match_internships = {match_internships}

# Free-text keywords: the terms you care about. A keyword is tagged onto a posting
# when it appears in the title, or is used at least twice in the description --
# a single passing mention in 5000 words of boilerplate means nothing.
keywords = [
{keywords}]

# false: keywords NARROW the internship feed -- they tag results so you can filter by
#        "python" on the site, but a keyword alone never pulls in a non-internship.
# true:  cast a wide net and surface any posting matching a keyword. ~10x the results,
#        and a lot more noise.
keyword_only_matches = {keyword_only_matches}

# Only keep postings matching one of these locations. Empty = anywhere. Matched
# word-boundaried against every location a board reports, including Ashby's
# "Remote (Canada)" secondary offices. List cities AND the country -- boards
# disagree on format. Avoid 2-letter codes: "CA" is California on most boards.
locations = [
{locations}]

# Title patterns that disqualify a posting outright.
exclude = [
{exclude}]
"""


def _toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_config(path=CONFIG):
    with open(path, "rb") as f:
        return tomllib.load(f)


def write_config(cfg, path=CONFIG):
    """Serialize the handful of settings the GUI owns. Not a general TOML writer."""
    def items(key):
        return "".join(f"    {_toml_str(v)},\n" for v in cfg.get(key, []) if v.strip())

    path.write_text(TEMPLATE.format(
        max_age_days=int(cfg["max_age_days"]),
        snippet_chars=int(cfg.get("snippet_chars", 300)),
        match_internships=str(bool(cfg["match_internships"])).lower(),
        keyword_only_matches=str(bool(cfg["keyword_only_matches"])).lower(),
        keywords=items("keywords"),
        locations=items("locations"),
        exclude=items("exclude"),
    ), encoding="utf-8")


class App:
    def __init__(self, root):
        self.root = root
        self.jobs = []
        self.q = queue.Queue()
        self.proc = None
        root.title("ATS Job Scraper")
        root.geometry("1180x680")
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        self._build_config_panel(root)
        self._build_results_panel(root)
        self._build_statusbar(root)

        self.load_config_into_form()
        self.load_feed()
        root.after(100, self._drain)

    # ---------------------------------------------------------------- config pane
    def _build_config_panel(self, root):
        f = ttk.LabelFrame(root, text="What to hunt for", padding=10)
        f.grid(row=0, column=0, sticky="nsw", padx=(10, 6), pady=10)
        f.rowconfigure(7, weight=1)
        f.rowconfigure(9, weight=1)

        row = ttk.Frame(f)
        row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(row, text="Max age (days)").pack(side="left")
        self.max_age = tk.IntVar()
        ttk.Spinbox(row, from_=1, to=365, width=6, textvariable=self.max_age).pack(side="right")

        self.internships = tk.BooleanVar()
        ttk.Checkbutton(f, text="Match internships / new-grad (by title)",
                        variable=self.internships).grid(row=1, column=0, sticky="w")

        self.kw_only = tk.BooleanVar()
        ttk.Checkbutton(f, text="Keywords alone can match (wide net)",
                        variable=self.kw_only).grid(row=2, column=0, sticky="w")
        ttk.Label(f, text="Off: keywords only tag internships.\nOn: ~10x results, much noisier.",
                  foreground="#666", font=("", 8)).grid(row=3, column=0, sticky="w", pady=(0, 8))

        ttk.Label(f, text="Keywords (one per line)").grid(row=6, column=0, sticky="w")
        self.keywords = tk.Text(f, width=34, height=10, wrap="none")
        self.keywords.grid(row=7, column=0, sticky="nsew", pady=(2, 8))

        ttk.Label(f, text="Locations (blank = anywhere)").grid(row=4, column=0, sticky="w")
        self.locations = tk.Text(f, width=34, height=5, wrap="none")
        self.locations.grid(row=5, column=0, sticky="nsew", pady=(2, 8))

        ttk.Label(f, text="Exclude these title words").grid(row=8, column=0, sticky="w")
        self.exclude = tk.Text(f, width=34, height=7, wrap="none")
        self.exclude.grid(row=9, column=0, sticky="nsew", pady=(2, 8))

        btns = ttk.Frame(f)
        btns.grid(row=10, column=0, sticky="ew")
        ttk.Button(btns, text="Revert", command=self.load_config_into_form).pack(side="left")
        ttk.Button(btns, text="Save", command=self.save_form).pack(side="left", padx=4)
        self.run_btn = ttk.Button(btns, text="Save && Run scrape", command=self.run)
        self.run_btn.pack(side="right")

    # --------------------------------------------------------------- results pane
    def _build_results_panel(self, root):
        f = ttk.Frame(root, padding=(0, 10, 10, 10))
        f.grid(row=0, column=1, sticky="nsew")
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

        bar = ttk.Frame(f)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(bar, text="Filter").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.refresh_tree())
        ttk.Entry(bar, textvariable=self.filter_var, width=32).pack(side="left", padx=6)
        self.new_only = tk.BooleanVar()
        ttk.Checkbutton(bar, text="New only", variable=self.new_only,
                        command=self.refresh_tree).pack(side="left")
        self.count_lbl = ttk.Label(bar, text="", foreground="#666")
        self.count_lbl.pack(side="right")

        cols = ("new", "date", "company", "title", "location", "tags")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c, w, t in [("new", 44, ""), ("date", 88, "Posted"), ("company", 120, "Company"),
                        ("title", 330, "Title"), ("location", 190, "Location"),
                        ("tags", 150, "Tags")]:
            self.tree.heading(c, text=t, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, anchor="w", stretch=(c == "title"))
        self.tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("new", foreground="#1d4ed8")
        self.tree.bind("<Double-1>", self.open_selected)
        self.tree.bind("<Return>", self.open_selected)

        ttk.Label(f, text="Double-click a row to open the posting",
                  foreground="#666", font=("", 8)).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.sort_key, self.sort_desc = "date", True

    def _build_statusbar(self, root):
        bar = ttk.Frame(root, padding=(10, 0, 10, 8))
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.status = ttk.Label(bar, text="Ready", anchor="w")
        self.status.grid(row=0, column=0, sticky="ew")
        self.bar = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self.bar.grid(row=0, column=1, sticky="e")

    # -------------------------------------------------------------------- config
    def load_config_into_form(self):
        cfg = read_config()
        self.max_age.set(cfg.get("max_age_days", 45))
        self.internships.set(cfg.get("match_internships", True))
        self.kw_only.set(cfg.get("keyword_only_matches", False))
        for widget, key in ((self.keywords, "keywords"), (self.exclude, "exclude"),
                            (self.locations, "locations")):
            widget.delete("1.0", "end")
            widget.insert("1.0", "\n".join(cfg.get(key, [])))
        self.status.config(text="Config loaded")

    def form_config(self):
        def lines(w):
            return [ln.strip() for ln in w.get("1.0", "end").splitlines() if ln.strip()]
        return {
            "max_age_days": self.max_age.get(),
            "snippet_chars": read_config().get("snippet_chars", 300),
            "match_internships": self.internships.get(),
            "keyword_only_matches": self.kw_only.get(),
            "keywords": lines(self.keywords),
            "exclude": lines(self.exclude),
            "locations": lines(self.locations),
        }

    def save_form(self):
        try:
            write_config(self.form_config())
        except (OSError, ValueError, KeyError) as e:
            messagebox.showerror("Could not save config", str(e))
            return False
        self.status.config(text=f"Saved {CONFIG.name}")
        return True

    # --------------------------------------------------------------------- scrape
    def run(self):
        if self.proc:
            return
        if not self.save_form():
            return
        self.run_btn.config(state="disabled")
        self.bar.start(12)
        self.status.config(text="Scraping 67 boards...")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        """Subprocess rather than importing scrape: a crash or hang cannot take the UI
        with it, and stdout stays clean."""
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-u", str(HERE / "scrape.py")],
                cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in self.proc.stdout:
                if line.strip():
                    self.q.put(("log", line.strip()))
            self.proc.wait()
            self.q.put(("done", self.proc.returncode))
        except OSError as e:
            self.q.put(("done", f"failed to start: {e}"))
        finally:
            self.proc = None

    def _drain(self):
        """tkinter is not thread-safe -- the worker posts to a queue, the UI thread reads."""
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.status.config(text=payload)
                else:
                    self.bar.stop()
                    self.run_btn.config(state="normal")
                    if payload not in (0, None):
                        messagebox.showerror("Scrape failed", f"scrape.py exited: {payload}")
                    else:
                        self.load_feed()
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    # ---------------------------------------------------------------------- feed
    def load_feed(self):
        if not FEED.exists():
            self.status.config(text="No results yet -- hit Save & Run scrape")
            return
        try:
            data = json.loads(FEED.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self.status.config(text=f"Could not read out/jobs.json: {e}")
            return
        self.jobs = data.get("jobs", [])
        self.refresh_tree()
        self.status.config(
            text=f"{data.get('count', 0)} roles from {data.get('boards', 0)} boards "
                 f"| updated {data.get('generated_at', '?')}")

    def sort_by(self, col):
        self.sort_desc = not self.sort_desc if col == self.sort_key else True
        self.sort_key = col
        self.refresh_tree()

    def visible(self):
        needle = self.filter_var.get().strip().lower()
        out = []
        for j in self.jobs:
            if self.new_only.get() and not j.get("is_new"):
                continue
            hay = (f"{j['title']} {j['company']} "
                   f"{' '.join(j.get('locations') or [j.get('location','')])} "
                   f"{' '.join(j.get('tags', []))} {j.get('snippet','')}").lower()
            if not needle or needle in hay:
                out.append(j)
        keys = {"new": lambda j: j.get("is_new", False), "date": lambda j: j.get("posted_at") or "",
                "company": lambda j: j["company"].lower(), "title": lambda j: j["title"].lower(),
                "location": lambda j: j.get("location", "").lower(),
                "tags": lambda j: ",".join(j.get("tags", []))}
        return sorted(out, key=keys[self.sort_key], reverse=self.sort_desc)

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        rows = self.visible()
        for j in rows:
            self.tree.insert("", "end", iid=j["key"], tags=("new",) if j.get("is_new") else (),
                             values=("NEW" if j.get("is_new") else "",
                                     j.get("posted_at") or "", j["company"], j["title"],
                                     " / ".join(j.get("locations") or [j.get("location", "")]),
                                     ", ".join(j.get("tags", []))))
        self.count_lbl.config(text=f"{len(rows)} of {len(self.jobs)}")

    def open_selected(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        job = next((j for j in self.jobs if j["key"] == sel[0]), None)
        if job and job.get("url"):
            webbrowser.open(job["url"])


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # Windows default is dated
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
