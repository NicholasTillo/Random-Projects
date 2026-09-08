// Server component. Drop into your Next.js app (app router) and render <JobBoard />.
//
// Fetching server-side means the JSON never crosses the browser's origin check and
// the page is server-rendered for SEO. The feed does send Access-Control-Allow-Origin: *
// if you'd rather fetch it client-side.
import JobList, { type Feed } from "./JobList";

const FEED =
  "https://raw.githubusercontent.com/NicholasTillo/Random-Projects/jobs-data/jobs.json";

export default async function JobBoard() {
  // Scraper runs every 6h; revalidating hourly is plenty and keeps this off the
  // critical path. raw.githubusercontent.com caches for 5 min on its own anyway.
  const res = await fetch(FEED, { next: { revalidate: 3600 } });

  if (!res.ok) {
    return (
      <p style={{ color: "#b45309" }}>
        Job feed unavailable (HTTP {res.status}). It republishes every 6 hours.
      </p>
    );
  }

  const feed: Feed = await res.json();
  return <JobList feed={feed} />;
}
