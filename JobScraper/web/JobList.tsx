"use client";

// All filtering is client-side over an already-loaded array -- the feed is ~65KB,
// so there is nothing to paginate and no API to call.
import { useMemo, useState } from "react";

export type Job = {
  key: string;
  ats: "greenhouse" | "lever" | "ashby";
  company: string;
  title: string;
  location: string;
  url: string;
  posted_at: string | null;
  first_seen: string;
  is_new: boolean;
  tags: string[];
  snippet: string;
};

export type Feed = {
  generated_at: string;
  boards: number;
  count: number;
  jobs: Job[];
};

const S = {
  input: {
    padding: "8px 10px",
    border: "1px solid #d4d4d8",
    borderRadius: 6,
    fontSize: 14,
    flex: "1 1 220px",
  },
  chip: (on: boolean) => ({
    padding: "4px 10px",
    borderRadius: 999,
    border: `1px solid ${on ? "#2563eb" : "#d4d4d8"}`,
    background: on ? "#2563eb" : "transparent",
    color: on ? "#fff" : "inherit",
    fontSize: 12,
    cursor: "pointer",
  }),
  card: {
    padding: "12px 0",
    borderTop: "1px solid #e4e4e7",
    display: "flex",
    gap: 12,
    justifyContent: "space-between",
  },
} as const;

export default function JobList({ feed }: { feed: Feed }) {
  const [q, setQ] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [newOnly, setNewOnly] = useState(false);

  const tags = useMemo(
    () => [...new Set(feed.jobs.flatMap((j) => j.tags))].sort(),
    [feed.jobs],
  );

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return feed.jobs.filter((j) => {
      if (newOnly && !j.is_new) return false;
      if (tag && !j.tags.includes(tag)) return false;
      if (!needle) return true;
      // Only these fields ship from the scraper -- full descriptions stay server-side.
      return `${j.title} ${j.company} ${j.location} ${j.snippet} ${j.tags.join(" ")}`
        .toLowerCase()
        .includes(needle);
    });
  }, [feed.jobs, q, tag, newOnly]);

  return (
    <section>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <input
          style={S.input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by title, company, location…"
          aria-label="Filter jobs"
        />
        <button style={S.chip(newOnly)} onClick={() => setNewOnly((v) => !v)}>
          New only
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {tags.map((t) => (
          <button
            key={t}
            style={S.chip(tag === t)}
            onClick={() => setTag(tag === t ? null : t)}
            aria-pressed={tag === t}
          >
            {t}
          </button>
        ))}
      </div>

      <p style={{ fontSize: 13, opacity: 0.7, margin: "0 0 4px" }}>
        {shown.length} of {feed.count} roles across {feed.boards} boards · updated{" "}
        <time dateTime={feed.generated_at}>
          {new Date(feed.generated_at).toLocaleString()}
        </time>
      </p>

      {shown.map((j) => (
        <article key={j.key} style={S.card}>
          <div style={{ minWidth: 0 }}>
            <a
              href={j.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontWeight: 600, textDecoration: "none" }}
            >
              {j.title}
            </a>
            {j.is_new && (
              <span style={{ ...S.chip(true), marginLeft: 8, padding: "2px 7px" }}>
                NEW
              </span>
            )}
            <div style={{ fontSize: 13, opacity: 0.75, margin: "2px 0 6px" }}>
              {j.company}
              {j.location && ` · ${j.location}`}
              {j.posted_at && ` · posted ${j.posted_at}`}
            </div>
            <p
              style={{
                fontSize: 12,
                opacity: 0.6,
                margin: 0,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {j.snippet}
            </p>
          </div>
          <span style={{ fontSize: 11, opacity: 0.5, whiteSpace: "nowrap" }}>{j.ats}</span>
        </article>
      ))}

      {shown.length === 0 && (
        <p style={{ opacity: 0.6, fontSize: 14 }}>Nothing matches those filters.</p>
      )}
    </section>
  );
}
